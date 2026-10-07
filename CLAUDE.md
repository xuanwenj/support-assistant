# CLAUDE.md

Standing rules for working in this repo. See [ARCHITECTURE.md](ARCHITECTURE.md) for the full plan, phases, and rationale.

## Architecture (locked in)

- RAG is self-contained: a single pipeline (ingest → retrieve → generate) that takes a question and returns an answer directly. No agent wrapping around it.
- Two backend tools, not one:
  - Product/policy docs (manuals, contracts, service terms) → RAG over a vector DB.
  - Customer/order data → structured queries only (predefined lookup functions) against PostgreSQL (Supabase), **never RAG**. This data is transactional and needs to be exact, not similarity-retrieved.
- Frontend is Next.js: question input, answer display with source citations, entry points for both features.
- Routing between the two tools is a Claude tool-use loop (`router.py`): the model picks database lookup functions or document search per question and can chain them. It only calls predefined tools, never writes SQL.
- Multi-agent orchestration (CrewAI Researcher/Writer) is not committed to — the structured-query tool now exists and the tool-use loop covers routing, so only add it if that stops being enough.

## Non-negotiables

- The customer/order tool must enforce authorization checks — never allow unrestricted/free-form queries against the customer or order tables. No LLM-generated SQL against these tables; use predefined, parameterized query functions only.
- Redact PII (names, contact info, order amounts) from logs.
- Don't index internal pricing/contract terms into the vector DB without access control on retrieval.
- Supabase/Postgres connection string and keys live in environment variables only, never committed.

## Stack

- Orchestration: none yet — RAG runs as a plain pipeline; CrewAI is a Phase 2 maybe, not a given
- LLM: Claude
- Vector DB: Chroma for MVP, evaluate Qdrant/Pinecone/Weaviate later
- Structured DB: PostgreSQL via Supabase (free tier) — replaces local CSV for products, price list, customers, orders
- Frontend: Next.js
- Backend: FastAPI
