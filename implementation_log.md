# Implementation Log

Record of what was actually built: plan, structure, content, result. One entry per concrete implementation, appended in order. `dev_journal.md` holds the outline (current step, decisions, problems) — details belong here.

Entry template: **Plan** (what and why) · **Structure** (files, functions, signatures) · **Content** (how it works, notable details) · **Result** (what was verified, known gaps).

---

## 1. RAG pipeline split into ingest.py and retrieval.py

**Plan.** The Phase 2 router needs to reuse retrieval without triggering ingestion, and without the generation step. Split the single `ingest_test.py` script in two and guard ingestion behind `__main__`.

**Structure.**
- `ingest.py` — `read_docx`, `read_pdf`, `load_file`, `chunk_text`; ingestion loop runs only under `if __name__ == "__main__"`.
- `retrieval.py` — `DISTANCE_THRESHOLD = 1.6`; `retrieve_relevant_chunks(collection, question, n_results=3, distance_threshold=DISTANCE_THRESHOLD)` returns `[{"text", "distance", "metadata"}]`; demo question + Claude generation under `__main__`.

**Content.**
- Ingestion reads `data/metadata.json` and only ingests files with `route == "rag"` (so `price-list.csv` is excluded by design, not by file extension).
- Chunking: split on blank lines; for `customer-faq.md` keep only chunks starting with `**Q:`.
- Each chunk is stored in Chroma collection `knowledge_base` (`./chroma_data`) with metadata `source_file`, `audience` (comma-joined string, because Chroma metadata values can't be lists), `source_system`.
- Retrieval takes the collection as an argument (no globals), so callers can pass their own.

**Result.** 125 chunks indexed. Importing `retrieval` has no side effects. Dripping-tap question answered correctly end to end. Committed as `cb04def`.

---

## 2. Supabase PostgreSQL schema and seed data

**Plan.** Replace the CSV/local files with real tables for structured data, per Phase 2 of `ARCHITECTURE.md`. Truncate + reseed during development.

**Structure.** Four tables, created in the Supabase SQL Editor:
- `customers` (customer_id PK text, name, email unique, phone, account_type retail/trade, region, created_at)
- `products` (product_code PK text, name, category, type, material, min/max_pressure_kpa, warranty_terms free text, retail_price_nzd, trade_price_nzd)
- `orders` (order_id PK text, customer_id FK, order_date, status pending/delivered/partially_returned/returned/cancelled)
- `order_items` (order_item_id bigint identity PK, order_id FK, product_code FK, quantity > 0, unit_price_charged)

**Content.**
- Row Level Security enabled on all four tables with no policies (deny-all for the `anon`/`authenticated` roles). The backend connects as `postgres` via `DATABASE_URL`, which RLS doesn't restrict.
- Seed: 11 products (all of `price-list.csv` merged with specs from `product-catalog.docx`; unknown values left NULL), 5 customers (3 retail, 2 trade), 5 orders, 6 line items. ORD-1003 is the bundle case: SH-203 at 349.00 and PC-110 at 49.00, both below retail, which is why `unit_price_charged` is stored per line.
- `DATABASE_URL` in `.env` uses the **Session pooler** string (user `postgres.<project-ref>`). The direct-connection host is IPv6-only and doesn't resolve on this network.

**Result.** Tables and seed loaded; counts verified from Python (5 customers). **Gap:** the schema and seed SQL were run in the SQL Editor and are not saved in the repo yet, so the truncate + reseed workflow isn't reproducible from git.

---

## 3. Database connection helper and query functions

**Plan.** Fixed, parameterized query functions only — no LLM-generated SQL — one function per lookup.

**Structure.**
- `db.py` — `get_connection()`: `psycopg.connect(os.environ["DATABASE_URL"])`. New connection per call, no pooling.
- `queries.py` — `get_order(order_id)`, `get_orders_by_username(username)`, `get_product(product_code)`; demo under `__main__`. Driver: `psycopg[binary]` 3.2.13.

**Content.**
- All queries use `%s` placeholders with values passed separately, and `dict_row` so rows are dicts.
- `get_order` → order dict with an `items` list (joined to `products` for the name), or `None`.
- `get_orders_by_username` → list of order dicts each with `items`, `[]` if no match. Joins `orders` to `customers` on `customer_id` and filters `customers.name = %s`.
- `get_product` → product dict, or `None`.
- Postgres `numeric` comes back as `Decimal` and dates as `datetime.date`.

**Result.** Checked by hand against the seed data: ORD-1003 returns both line items at bundle prices; unknown order/product → `None`; `Grace Kim` → one order; unknown name → `[]`. Bugs found and fixed along the way in `get_orders_by_username`: filtered on the wrong column, ambiguous `customer_id` after the join, per-order query ran after the cursor closed, and returned a single order instead of the list. **Known quirks:** names aren't unique, so it can return orders from several customers; the function is named "username" but matches `customers.name`.

---

## 4. Claude tool-use router (tools.py, router.py, test_router.py)

**Plan.** Let Claude choose between the database functions and document search for a free-text question, chaining calls when a question needs both. Manual loop with an iteration cap; RAG exposed to the router as retrieval-only (raw chunks), not a generated answer.

**Structure.**
- `tools.py` — `TOOL_SCHEMAS` (4 tools), `TOOL_FUNCTIONS` dispatch map, `search_documents(question)` wrapper, `run_tool(name, tool_input)` → `(content, is_error)`.
- `router.py` — `MODEL = "claude-haiku-4-5"` (first built and tested on `claude-opus-5-5`, switched to Haiku afterwards to cut cost and latency), `MAX_ITERATIONS = 5`, `SYSTEM_PROMPT`, `answer_question(question, client=None, max_iterations=5)` → `{"answer", "tool_calls"}`.
- `test_router.py` — `unittest`; offline tests with a scripted `FakeClient`, live tests gated behind `RUN_LIVE_TESTS=1`.

**Content.**
- Tools exposed to Claude: `get_order`, `get_orders_by_username`, `get_product`, `search_documents` (wraps `retrieve_relevant_chunks`, returns `text`, `source_file`, `distance`; Chroma collection opened lazily and cached).
- Loop: send question + tools + system prompt → if `stop_reason` is `tool_use`, append the assistant content unchanged, run every `tool_use` block, return all `tool_result` blocks in one user message, repeat → stop on any other reason. `refusal` returns a fixed message; hitting the cap returns "Stopped after N tool rounds…".
- Serialization: `json.dumps(result, default=str)` so `Decimal` and `date` become strings.
- Tool failures become `is_error` results carrying only the exception type, not its message. Tool inputs and results are never logged (PII rule in `CLAUDE.md`).
- Requests go through `client.beta.messages.create` with server-side fallback enabled (`betas=["server-side-fallback-2026-07-01"]`, `fallbacks="default"`).
- System prompt: internal-staff support assistant; answer only from tool results; cite the source file for document content; call several tools when needed; say so plainly when nothing is found.

**Result.** 17 tests pass. 12 offline (tool schemas match dispatch map, Decimal/date serialization, not-found results, unknown tool, error results, direct answer, result fed back with matching `tool_use_id`, parallel calls in one message, chaining across rounds, tool error continues the loop, iteration cap, refusal). 5 live (~137 s total on Opus 5.5, ~18 s for the whole suite on Haiku 4.5, all still passing; the server-side fallback parameter is accepted by Haiku): real ORD-1003 serializes with bundle prices; order status uses `get_order`; unknown order reported as not found; policy question uses only `search_documents`; compound question uses `get_orders_by_username` and `search_documents`. Read the compound answer: it chained 4 calls, cited sources, and stated it couldn't verify the refund because the database has no return record. **Not built yet:** `get_customer`, `get_customer_by_email`, `get_customer_by_phone`, `get_orders_for_customer`.
