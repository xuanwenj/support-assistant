# Multi-Agent Knowledge Assistant — Architecture & Project Plan

## 1. Requirements & Scope

- **Goal**: For the distributor business — user asks a question → system automatically retrieves relevant information (product docs, service terms, customer/order data) → generates a structured report/answer.
- **Key decision**: Product docs and service terms are unstructured documents, well-suited to RAG. Customer and order data is structured (lives in a database) — don't use RAG for that; query the database/API directly. This is more accurate and avoids the hallucination risk that comes with vector retrieval on transactional data.

## 2. Overall Architecture

```
User question
   │
   ▼
┌─────────────────────────────┐
│   Crew (orchestration, CrewAI) │
│                               │
│  Agent A: Researcher          │
│  - Classifies the question     │
│  - Calls the matching tool     │
│         │                     │
│         ▼                     │
│  Agent B: Writer/Analyst      │
│  - Synthesizes what Agent A    │
│    retrieved                   │
│  - Produces a structured       │
│    report/answer               │
└─────────────────────────────┘
         │           │
         ▼           ▼
┌────────────────┐ ┌──────────────────────┐
│ Tool 1:          │ │ Tool 2:                │
│ Product/policy RAG│ │ Customer/order lookup   │
│ (vector retrieval)│ │ (structured SQL/API call)│
└────────────────┘ └──────────────────────┘
        │                     │
        ▼                     ▼
  Vector database         Distributor's business DB
  (manuals/contracts/terms) (customer table/order table)
```

**Agent responsibilities**

- **Researcher**: Takes the user question, classifies/routes it (product question vs. customer/order question vs. both), calls the matching tool, hands raw retrieval results to the next agent. Chain via CrewAI `Task`s, or use `hierarchical` process to give it a manager-like coordination role.
- **Writer**: Doesn't touch data sources directly — only processes what Researcher hands it, and produces the final report in whatever format is needed (e.g. a briefing template for distributor staff).

## 3. Recommended Stack

| Layer                     | Recommendation                                                                                   | Notes                                                                                                                                  |
| ------------------------- | ------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| Multi-agent orchestration | **CrewAI**                                                                                       | If complexity grows, evaluate CrewAI Flows for more deterministic control flow, or compare against LangGraph                           |
| LLM                       | Claude (Sonnet for retrieval routing/tool calls; Sonnet/Opus for the Writer's report generation) | Tier cost: smaller model for simple lookups, larger model for report writing                                                           |
| Embeddings                | Voyage AI or OpenAI `text-embedding-3`                                                           | Open-source bge/e5 is fine too for small doc volumes                                                                                   |
| Vector database           | **Chroma** for MVP (local/lightweight), swap to Qdrant/Pinecone/Weaviate for production          | Don't start with a heavy vector DB                                                                                                     |
| Document parsing/chunking | `unstructured.io` or LlamaIndex loaders                                                          | For PDF/Word product manuals and service terms                                                                                         |
| Structured queries        | Wrap a read-only API over the existing DB, or a CrewAI Tool wrapping SQLAlchemy                  | Use predefined query functions (lookup by customer ID/order number) — never let the LLM freely generate SQL against the customer table |
| Backend service           | FastAPI exposing the Crew as an HTTP endpoint                                                    | Easiest integration path with existing distributor systems                                                                             |
| Observability             | CrewAI's built-in tracing, or Langfuse/Arize Phoenix                                             | Debugging agent decision paths and token spend                                                                                         |
| Evaluation                | Hand-built Q&A test set + RAGAS for the RAG portion                                              | See Phase 3 below                                                                                                                      |

## 4. Data & Security — Non-Negotiables

- The customer/order tool must enforce **authorization checks** (which account can see which customers). Never allow unrestricted queries against the full database.
- Redact PII (names, contact info, order amounts) in logs, especially when calling a cloud LLM API.
- If RAG-indexed product docs contain internal pricing/terms, apply access control there too.

## 5. Phased Build Plan

**Phase 0 — Requirements inventory**

- Confirm data sources: product doc formats, service terms documents, customer/order table schema.
- Use local files

**Phase 1 — MVP: single RAG pipeline**

- Build only the product docs + service terms RAG tool.
- Get Researcher + Writer working end-to-end on "question → retrieve → report."
- Run Chroma locally to validate prompts and agent division of labor.

**Phase 2 — Structured customer/order lookup**

- Build the second tool (structured query service) with predefined callable query functions.
- Add routing logic to Researcher: RAG tool, structured query tool, or both.
- Handle report generation when it needs to blend both data types.

**Phase 3 — Evaluation & tuning**

- Build a test set of realistic questions spanning both data sources.
- Evaluate the RAG portion with RAGAS (retrieval relevance/accuracy).
- Check how often the agent's routing picks the wrong tool.

**Phase 4 — Deployment & monitoring**

- Package with FastAPI + Docker.
- Wire up observability: token cost, latency, error rate.
- Add a feedback mechanism so users can flag wrong answers.

**Phase 5 — Iterate**

- Add specialized agents as usage patterns emerge (e.g. order-exception handling, returns workflow agent).
- If serving multiple distributors, design for tenant isolation.

## 6. Current Status

Project scaffold not yet started. Next step: Phase 0 (requirements inventory) — confirm product doc formats/location and customer/order data access (DB vs. API).
