# Implementation Log

Record of what was actually built: plan, structure, content, result. One entry per concrete implementation, appended in order. `dev_journal.md` holds the outline (current step, decisions, problems) — details belong here. Frontend features are logged separately in `frontend_implementation_log.md`.

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

**Result.** Tables and seed loaded; counts verified from Python (5 customers). **Gap:** the original schema and seed SQL were run in the SQL Editor and are not saved in the repo, so the truncate + reseed workflow isn't reproducible from git. Partly addressed in section 6: `schema.sql` (reconstructed structure) and `seed_test_data.sql` (test rows only) are now in the repo; the base seed data still isn't.

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

**Result.** 17 tests pass. 12 offline (tool schemas match dispatch map, Decimal/date serialization, not-found results, unknown tool, error results, direct answer, result fed back with matching `tool_use_id`, parallel calls in one message, chaining across rounds, tool error continues the loop, iteration cap, refusal). 5 live (~137 s total on Opus 5.5, ~18 s for the whole suite on Haiku 4.5, all still passing; the server-side fallback parameter is accepted by Haiku): real ORD-1003 serializes with bundle prices; order status uses `get_order`; unknown order reported as not found; policy question uses only `search_documents`; compound question uses `get_orders_by_username` and `search_documents`. Read the compound answer: it chained 4 calls, cited sources, and stated it couldn't verify the refund because the database has no return record. The four customer lookups that weren't built yet are in section 6.

---

## 5. HTTP layer (api.py) and source tracking in the router

**Plan.** The Next.js frontend needs an HTTP endpoint over `answer_question()`, and answers from documents must show their source files. The router returned only `(name, input)` pairs for tool calls, so it had no source data to hand back.

**Structure.**
- `api.py`: FastAPI app. `POST /ask` takes `{"question": str}` (1–2000 chars, stripped, blank rejected with 422) and returns `{"answer", "tools_used", "sources"}`. `GET /health`.
- `router.py`: new `_add_sources(sources, tool_name, content)`; `answer_question` now returns `{"answer", "tool_calls", "sources"}` on every exit path (normal, refusal, iteration cap).
- `test_api.py` (5 offline tests) and 3 new offline tests in `test_router.py`. `fastapi` installed into `.venv` (there is no `requirements.txt` yet).

**Content.**
- `sources` is the deduplicated, ordered list of `source_file` values from successful `search_documents` results. Other tools and failed searches contribute nothing, so no citation is invented.
- **`sources` means documents retrieved, not documents the answer relied on.** Live check: for "Is a dripping tap covered by warranty?" it returned `customer-faq.md` and `product-catalog.docx` while the answer cited only the FAQ. A stricter version would need the model to report which sources it used (e.g. a structured final answer).
- `/ask` is a plain `def` so FastAPI runs the blocking call in a worker thread. No CORS middleware, since only the Next.js server calls it (proxy design); run it bound to `127.0.0.1`.
- PII: no logging of questions or answers; `tools_used` returns tool names only (inputs hold customer names and order IDs); failures return a generic 502 with no exception text.

**Result.** 24 tests pass offline (5 skipped live tests unchanged). Live through uvicorn: ORD-1005 question returned `tools_used: ["get_order"]`, `sources: []`; the warranty question returned `["search_documents"]` with the two source files above; an empty question returned 422.
**Known gaps:** no authorization on `/ask` (see dev journal); `sources` over-reports as noted above.

---

## 6. Customer lookup functions (queries.py, tools.py, schema.sql)

**Plan.** Finish the remaining lookups so staff can find a customer or their orders by customer ID, email, phone or name. Read the real schema first, write the functions against it, register them as router tools, then test live. The single search box for `/lookup` (classify the input, call the matching function) is a separate backend step, not built here; the UI is being built on a separate branch.

**Structure.**
- `schema.sql`: table definitions reconstructed from `information_schema` and `pg_constraint` (2026-10-07), structure only. `customers` also has `region` (nullable) and `created_at`; `phone` is nullable; `order_item_id` is `generated always as identity`. Indexes beyond PK/unique are not captured.
- `seed_test_data.sql`: re-runnable test rows, a second customer named Grace Kim (`CUST-006`, `grace.kim.dunedin@example.com`, Dunedin) with `ORD-1006` (one `PC-101` at 189.00), so name lookups can return several customers. Includes the delete statements to remove them.
- `queries.py`: new `get_customer`, `get_customer_by_email`, `get_customer_by_phone`, `get_orders_for_customer`; helpers `_attach_items` and `_normalize_phone`.
- `tools.py`: 4 new schemas and dispatch entries (8 tools now). `router.py`: one system-prompt rule for several customers sharing a name.
- `test_queries.py` (new), plus new offline and live tests in `test_router.py`.

**Content.**
- Customer dicts carry `customer_id, name, email, phone, account_type, region` (explicit column list, `created_at` left out).
- `get_customer` / `get_customer_by_email` return one dict or `None`. Email match is `lower(email) = lower(trimmed input)`; email is unique.
- `get_customer_by_phone` returns a **list**, since phones are not unique. Both sides are reduced to digits and a leading `64` becomes `0` (`regexp_replace` in SQL, `_normalize_phone` in Python), so `021 555 0103`, `0215550103` and `+64 21 555 0103` match. Blank, non-numeric and null phones never match.
- `get_orders_for_customer` returns orders oldest first with items, `[]` for an unknown customer.
- `_attach_items` fetches every order's line items in one query (`order_id = any(%s)`), replacing the per-order loop. `get_order` and `get_orders_by_username` use it. Output of both matched a captured before-refactor baseline for all seed orders and customers.
- All queries stay predefined and parameterized; the only f-strings interpolate module-level column-list constants.
- Tool errors still return only the exception type (an unexpected extra argument comes back as `TypeError`).

**Result.** Offline: 42 tests pass (19 live skipped). Live DB (`test_queries.py`, 13 tests) pass, including both Grace Kims returned by the name lookup and told apart by email. Live router (8 tests, about 32 s on Haiku 4.5) pass: orders by email returns only `ORD-1006`, by phone only `ORD-1003`, and the shared-name question shows both customers' IDs. The new rows were inserted into the live Supabase data on 2026-10-07 (6 customers, 6 orders, 7 items).
**Observations.**
- For "Show me the orders for Grace Kim", Claude lists the two customers separately with their IDs and offers more detail; it does not ask which one is meant. Nothing is merged, so the prompt rule is met.
- For the compound question (Grace Kim's partial bundle return vs. policy), the answer said document search found no policy on partial bundle return pricing, and asked which Grace Kim was meant. The earlier run found material to reason about. The live test still passes (it only checks that both tools were called). Not investigated: could be the prompt change, the duplicate customer, or model variation.
- Live tests that mention "Grace Kim" now depend on `seed_test_data.sql` being loaded.

---

## 7. Lookup search backend (search.py, GET /lookup)

**Plan.** The `/lookup` page has one text box. The backend works out what was typed, finds the matching customers, and lets the page load one customer's orders once they are picked. Classification is plain code, not the LLM, so names, emails and phones never go to a cloud API.

**Structure.**
- `search.py` (new): `classify_query(text)` → `(kind, value)`; `search_customers(text)` → `{"type", "customers"}`; `customer_summary` with `mask_email` / `mask_phone`.
- `queries.py`: new `get_customers_by_name(name)` (case-insensitive exact match, returns every customer with that name).
- `api.py`: `GET /lookup?q=` and `GET /lookup/customers/{customer_id}`, with pydantic response models.
- `test_search.py` (new), plus new tests in `test_api.py` and `test_queries.py`.

**Content.**
- Classification order: `ORD-\d+` order ID, `CUST-\d+` customer ID (both case-insensitive, upper-cased), contains `@` email, only digits/space/`+-()` with at least 6 digits phone, otherwise name. `ORD-12A`, `ORD 1003` and `1003` fall through to name. Blank is `empty` and touches no lookup.
- Every kind returns the same shape, a list of customers. An order ID resolves to its customer (`get_order` then `get_customer`); phone and name can return several.
- `GET /lookup` returns `{"type", "customers": [...]}` where each customer is a summary: `customer_id, name, account_type, region, email_masked` (`g***@example.com`), `phone_masked` (`*** *** 0103`). Full email and phone only come from the detail endpoint. No match is `200` with an empty list; blank or over 200 chars is `422`; failures are a generic `502`. The query is not logged and not echoed in errors.
- `GET /lookup/customers/{customer_id}` returns `{"customer": {...full fields}, "orders": [... with items]}`; the ID must match `^CUST-\d+$` (otherwise `422` before any query); unknown is `404`. `unit_price_charged` and dates serialize as strings (`"349.00"`, `"2026-07-01"`).
- Python 3.9 in the venv, so models use `Optional[str]`, not `str | None`.

**Result.** 66 tests offline (25 live skipped); the 29 live DB tests pass (`test_queries`, `test_search`). Through uvicorn against Supabase: `grace kim` returned both customers; `ORD-1006` returned CUST-006; `+64 21 555 0103` returned CUST-003; unknown email returned an empty list; blank `422`; detail for CUST-006 returned her order with `"189.00"`; unknown ID `404`; malformed ID `422`.
**Known quirks.** The two Grace Kims' masked emails are identical (`g***@example.com`); the pick-list tells them apart by region and the last four phone digits. Name matching is exact (`Grace` finds nothing). No authorization on these endpoints, like `/ask`.
