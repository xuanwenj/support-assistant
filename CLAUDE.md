# CLAUDE.md

Standing rules for working in this repo. See [ARCHITECTURE.md](ARCHITECTURE.md) for the full plan, phases, and rationale.

## Architecture (locked in)

- Two-tier multi-agent design via CrewAI: **Researcher** agent (classifies question, calls tools) → **Writer** agent (synthesizes results into a report). Writer never touches data sources directly.
- Two backend tools, not one:
  - Product/policy docs (manuals, contracts, service terms) → RAG over a vector DB.
  - Customer/order data → structured queries only (predefined lookup functions), **never RAG**. This data is transactional and needs to be exact, not similarity-retrieved.

## Non-negotiables

- The customer/order tool must enforce authorization checks — never allow unrestricted/free-form queries against the customer or order tables. No LLM-generated SQL against these tables; use predefined query functions only.
- Redact PII (names, contact info, order amounts) from logs.
- Don't index internal pricing/contract terms into the vector DB without access control on retrieval.

## Stack

- Orchestration: CrewAI
- LLM: Claude
- Vector DB: Chroma for MVP, evaluate Qdrant/Pinecone/Weaviate later
- Backend: FastAPI
