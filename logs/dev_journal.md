build architecture diagram of this application
build a rag agent first
[the structural diagram](multi_agent_stack_architecture_v2.png)

# Phase 0 plan

- sort out the files in different formats, put them in data/
- label metadata at the top of the fils
- Classify data sources as RAG vs. structured query.

## Implementation steps:

- Environment setup (Python venv, install chromadb, embedding SDK)
  - Python 3.9.6.
  - create a virtual env
    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install --upgrade pip
    deactivate
- ingestion script: multi-format parsing (docx/pdf/md; skip csv)
- Chunking logic
- Generate embeddings + write to vector (Chroma)
- Metadata filtering integration (read metadata.json, handle the route field)
- Retrieval function + test against your FAQ questions
- A single Claude call to generate the final answer (skip CrewAI for now — just validate that retrieved content supports a decent answer)
- End-to-end debugging (this step usually takes longer than expected — chunk size and retrieval count often need back-and-forth tuning)

## Takeaways

- the RAG is a separated operation and maintained on it's own trigger, not on every UI interaction (in this case, a query/question)
- pros of separating RAG from the multi-agents apps are:
  - it can fail independently without affecting the main app
  - it has its own "health check" concern. You'd want to know things like: did the last ingestion run succeed? How many chunks are in the vector database? Is anything stale? This is a small monitoring habit, not a huge extra system.

# Phase 1 plan

- Build only the product docs + service terms RAG tool.
- Get Researcher + Writer working end-to-end on "question → retrieve → report."
- Run Chroma locally to validate prompts and agent division of labor.

## Decisions made along the phase 1

**Embeddings**
Choose local setup (chromadb), it bundles a small local embedding model no api key. Can swap later.

**How to call Claude? Raw anthropic SDK vs CrewAI**
Choose anthropic SDK over CrewAI, write a handful of lines: send a prompt, get a completion and then wrap it in a CrewAI agent later.

## The pipeline of RAG feature

**Ingestion** — your loader (md/pdf/docx → plain text), which we just talked through.
**Chunking** — splitting that text into smaller pieces before embedding. This is a real design decision: too large and retrieval gets imprecise (a chunk about "returns" also drags in unrelated SLA text); too small and you lose context. There are strategies (fixed character/token count, paragraph-based, with or without overlap between chunks) and no single right answer — it depends on your docs.
**Embedding + storage** — turning each chunk into a vector and writing it into a Chroma collection, along with metadata (which file it came from, maybe a chunk index) so you can cite sources later.
**Retrieval** — given a user's question, embed the question the same way, ask Chroma for the top-k most similar chunks.
**Augmentation + generation** — stuff those retrieved chunks into a prompt alongside the user's question, send it to Claude via the anthropic SDK, get back an answer grounded in your docs.

## Problems

**Irrelevant chunk retrieved due to non-content paragraph in FAQ doc**
Context: Testing retrieval with n_results=3 against customer-faq.md.

Problem: The 3rd result returned was the FAQ file's intro paragrap ("Collected from common customer questions...") — not an actual Q&A pair. It shares surface-level vocabulary with the query but isn't semantically relevant content.

Root Cause: Chunking splits on `---`, which treats the intro paragraph as its own standalone chunk — same status as any real Q&A pair, even though it's metadata/description text, not answerable content. n_results=3 also forces exactly 3 results regardless of whether a 3rd relevant match exists.

Solution: Filter out non-content paragraphs before chunking (e.g. skip segments without a "Q:" marker)

**The retriveled chunks are not always highly related to the query**
Context: Testing retrieval with n_results=3 against customer-faq.md.

Problem: n_results is a fixed count, not a relevance guarantee — it always returns exactly that many results, even if fewer (or none) are actually relevant.

```
results = collection.query(
    query_texts=["Is a dripping tap covered by warranty?"],
    n_results=3
)
```

Options Considered:

- Inspect distance scores to set a relevance threshold
- Add an AI reranking step to re-score retrieved chunks

## Upgrade the RAG loop

- Wrap the chunks and question with Claude AI, return a response
- Implement multi-formats ingestion with a dispachter

# Phase 2 plan

- Set up Supabase PostgreSQL for structured data (products, price list, customers, orders).
- Build the structured-query tool with predefined, parameterized query functions only.
- Build the Next.js frontend.

## Decisions made along the phase 2

1. Seeding strategy: truncate + reseed vs. idempotent upserts
   Choose truncate + reseed during development. Mock data will change frequently while iterating on schema and test cases, so resetting to a known state is simpler than maintaining upsert logic. Revisit idempotent seeding only if this needs to run against a persistent environment later.

2. Schema: 4 tables — customers, products, orders, order_items

- customers (customer_id PK, name, email, phone, account_type [retail/trade], region, created_at)
- products (product_code PK, name, category, type, material, min/max_pressure_kpa, warranty_terms, retail_price_nzd, trade_price_nzd)
- orders (order_id PK, customer_id FK, order_date, status)
- order_items (order_item_id PK, order_id FK, product_code FK, quantity, unit_price_charged)

3. price_list merged into products, not a separate table
   price-list.csv is 1:1 with product code and has no independent lifecycle, so a join would just add friction for no benefit.

4. unit_price_charged stored per line item, not derived from products.retail_price_nzd\*\*
   Needed to represent bundle-adjusted pricing — e.g. a diverter valve sold below its normal retail price as part of a twin shower bundle. Without this, a partial bundle return can't be recalculated against individual retail pricing, which staff-troubleshooting-notes.md flags as a real recurring problem.

5. warranty_terms as free text, not structured columns
   The structured-query tool only needs to look up one product's warranty and state it, not filter/compare products by warranty length — so the queryability structured columns (warranty_years_primary/secondary) would add isn't worth the nullable-column complexity.

6. will implement gerneral query,
   todo: extract retrieval into it's own function:
   Pull the retrieval + distance-threshold-filtering logic out of ingest_test.py into a standalone function (e.g. retrieve_relevant_chunks(question) → filtered chunks with their source metadata). The standalone script keeps using it followed by its own generation call; the router will call the same function and skip generation.

## Mock data sketch

5 customers (mix of retail/trade accounts) and 5 orders, chosen to map to real scenarios the docs already describe rather than arbitrary filler:

- ORD-1001 — warranty lookup case (ties to the "dripping tap" FAQ question)
- ORD-1002 — straightforward trade-pricing case
- ORD-1003 — partial bundle return (twin shower set + diverter valve) — the messiest real case, from staff-troubleshooting-notes.md
- ORD-1004 — trade account, ambiguous personal-use purchase (the "gray area" case)
- ORD-1005 — pending order, for order-status questions

**Change the PostgresSQL retrieval stratgy**
Before: write fixed functions and wire up Claude tool-sue to let AI pick which function and agrguments.
Now: simple SQL retrivial
Reason to change: the question types are predictable and the data is sensitive, and also I reaslised the queries of orders by searching name, phone, or emails doesn't need a llm to analyse, it's straightforward.
The prep work should be updated

# Phase 2 Implementing structured-SQL retrieval

## Prepare work

**Choose fixed query functions over general query interace( text-to-SQL )**
Reasons:

- data security, if leave the sql function to LLM, the AI could be tricked into retrieving every customer's address and phone numbe through prompt injection.
- accuracy
- testability, fixed functions is easier to test the output one by one

But in a customer support context, the question types are predictable and the data is sensitive, so I chose a fixed set of query functions, trading flexibility for security, accuracy, and testability. If I later build a data analysis feature for internal staff, that's where text-to-SQL would make sense, and I'd pair it with read-only database permissions.

It's not choosing fixed functions over general query interace. the latter is for mixed questions.

**How the LLM fits in**
LLM doesn't write SQL, it needs to choose which functions to call when gets a question, When implementing general query

**Paramerised queries, not string formatting**

Inside each function, the argument gets passed to the database driver as a parameter/placeholder, never interpolated into a SQL string directly. This is what actually prevents SQL injection

**What can be improved**

- authorization boundary should be a property of the functioin signatures, because i haven't implemented auth/login system yet.

# Implementation steps

1. Add the Postgres driver
2. A connection helper
3. Write fixed query functions
4. test the functions
5. wire up Claude tool-use

**Steps of wiring up Claude tool-use**

1. Describe the 4 tools to Claude
   For each function (get_order, get_orders_by_username, get_product, retrieve_relevant_chunks), you write a schema: its name, a plain-English description of what it does and when to use it, and what argument(s) it expects. This is literally what Claude reads to decide which tool fits a given question — the quality of the description matters a lot here, since it's the only thing standing in for "read the source code."

2. Build a dispatch map
   A dictionary from tool name (string) → the actual Python function. When Claude says "call get_order with order_id=ORD-1003," your code needs to turn that string "get_order" into an actual call to your get_order function. This is just {"get_order": get_order, "get_orders_by_username": get_orders_by_username, ...} — a lookup table, nothing clever.

3. Write the system prompt
   Tell Claude what it is and how to behave: it's a support assistant, it must answer only using what the tools return (not general knowledge or guesses), and it should use the tools rather than trying to answer from the question alone. This is the same grounding instinct as your RAG prompt ("answer using only the context below"), just extended to cover tool results too.

4. The loop itself
   This is the part that's genuinely new (not just "one call" like RAG's generation step):

Send the question + tool schemas + system prompt to Claude.
Look at the response. If it contains one or more tool_use blocks, that's Claude asking to call specific tools with specific arguments.
For each one, look it up in your dispatch map, call the real function, get the result.
Send those results back to Claude as tool_result blocks, appended to the conversation.
Call Claude again with the updated conversation. Repeat from step 2.
When a response comes back with no tool_use blocks — just plain text — that's the final answer, and the loop ends.
This is what lets compound questions work without any special-casing: for "was Grace Kim's return priced correctly," Claude might call get_orders_by_username first, see the order, then in the next turn decide it also needs retrieve_relevant_chunks for the bundle-return policy — the loop just keeps going until it has what it needs.

5. A concrete snag you'll hit: tool results aren't JSON-safe as-is
   You already saw this — your query functions return Decimal and datetime.date values (from unit_price_charged, order_date). Tool results have to be sent back to Claude as text/JSON, and neither of those types serializes automatically. You'll need to convert them (e.g. to strings) before packing a result into a tool_result block.

6. A safety cap on iterations
   Cap the loop at some max number of rounds (e.g. 5). If something goes wrong and Claude keeps requesting tools without ever settling on an answer, you don't want it looping forever.

7. Test both solo and compound questions
   Solo: "what's the status of order ORD-1005" (one tool call, done). Compound: "was Grace Kim's return priced correctly" (customer/order lookup, then RAG for policy, then synthesis) — this is the case that actually proves the loop is doing more than a single function call.

# Progress outline

Implementation details (plan, structure, content, results) live in [implementation_log.md](implementation_log.md). This file only tracks the current step, decisions and problems.

**Current step:** Phase 2, structured-query steps 1–5 done (driver, connection helper, query functions, tests, Claude tool-use router). Next: remaining lookup functions (customer by email/phone), update CLAUDE.md/ARCHITECTURE.md for the router, then the Next.js frontend (scaffolded; routes, nav and `QuestionBox` client component done; FastAPI `POST /ask` with sources done; proxy route handler `app/api/ask/route.ts` and the wired question box with answer and sources done and checked in the browser; next: Markdown rendering for answers, the `/lookup` page, authorization).

**Decisions**

- Claude routes free-text questions (RAG vs. SQL, chained when needed) via tool use. This supersedes the "simple SQL retrieval" note above; a dedicated staff lookup form can still call the functions directly without an LLM.
- RAG is exposed to the router as retrieval only (raw chunks). The standalone RAG script keeps its own generation step.
- Ingestion and retrieval split into separate files so the router can import retrieval without re-running ingestion.
- Lookup feature is for internal staff; lookups by name, email, phone (membership dropped).
- Build 4 tools first (`get_order`, `get_orders_by_username`, `get_product`, document search); the other lookups wait until the loop is proven.
- Manual tool-use loop with a 5-round cap rather than the SDK tool runner.
- Router model set to Haiku 4.5 for now (cheaper and faster; live tests still pass).
- Frontend: Next.js in `frontend/`, browser talks to a Next.js route handler that proxies to FastAPI (no CORS, backend URL stays server-only). Working style: user writes the code, Claude reviews and supplies snippets on request. CORS notes are in [frontend_implementation_log.md](frontend_implementation_log.md).
- Frontend double submit: block while a request is in flight (disabled button plus an early return in the handler) instead of cancel-and-replace, because aborting in the browser doesn't stop the paid backend call.

**Problems**

- Supabase direct connection is IPv6-only and didn't resolve → use the Session pooler connection string.
- venv `pip` script has the old folder name baked in → use `python -m pip`; the shell's `python` can resolve to conda → call `.venv/bin/python`.
- `get_orders_by_username` had several bugs (wrong column, ambiguous join column, closed cursor, returned one order) → fixed.
- Schema and seed SQL aren't saved in the repo yet, so reseeding isn't reproducible.
- **OPEN: no authorization on `POST /ask`.** `CLAUDE.md` requires authorization checks on customer/order data, but `api.py` has none, so anyone who can reach port 8000 can query any customer or order through the router. Fine only while bound to `127.0.0.1` in development. Needs a decision before anything is shared or deployed: who the staff users are, how they authenticate (e.g. Supabase Auth or a shared secret between the Next.js server and FastAPI as a minimum), and which accounts may see which customers. The checks must be enforced in the backend, not the frontend.
- `sources` returned by `/ask` are documents retrieved, not necessarily documents the answer used (e.g. product-catalog.docx listed while the answer cited only the FAQ). Acceptable for now; revisit if it misleads.
