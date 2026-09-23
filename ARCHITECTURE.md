# Multi-Agent Knowledge Assistant — Architecture & Project Plan

## 1. Requirements & Scope

- **Goal**: For the distributor business — user asks a question → system automatically retrieves relevant information (product docs, service terms, customer/order data) → generates a structured report/answer.
- **Key decision**: Product docs and service terms are unstructured documents, well-suited to RAG. Customer and order data is structured (lives in a database) — don't use RAG for that; query the database/API directly. This is more accurate and avoids the hallucination risk that comes with vector retrieval on transactional data.
- **Stack note (2026-09-23)**: Next.js (frontend) and PostgreSQL (structured data) were added deliberately, on top of the technical rationale, to give this project real experience with a stack combination common in AI product roles.

## 2. Overall Architecture

> **Status update (2026-09-23):** The Researcher/Writer CrewAI split below was the original plan, but the RAG tool turned out to be self-contained (ingest → retrieve → generate in one pipeline, no agent needed to wrap it). Agent orchestration is deferred — revisit once the structured-query tool exists in Phase 2, only if routing between the two tools actually requires it.

```
Next.js frontend
(question input, answer + citations, entry points for both features)
   │
   ▼
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
│ (vector retrieval)│ │ (structured SQL via     │
│                    │ │  predefined functions)  │
└────────────────┘ └──────────────────────┘
        │                     │
        ▼                     ▼
  Vector database         PostgreSQL (Supabase)
  (manuals/contracts/terms) (products, price list, customers, orders)
```

**Agent responsibilities**

- **Researcher**: Takes the user question, classifies/routes it (product question vs. customer/order question vs. both), calls the matching tool, hands raw retrieval results to the next agent. Chain via CrewAI `Task`s, or use `hierarchical` process to give it a manager-like coordination role.
- **Writer**: Doesn't touch data sources directly — only processes what Researcher hands it, and produces the final report in whatever format is needed (e.g. a briefing template for distributor staff).

## 3. Recommended Stack

| Layer                     | Recommendation                                                                                   | Notes                                                                                                                                  |
| ------------------------- | ------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| Frontend                  | **Next.js**                                                                                       | Question input, answer display with source citations, entry points for document Q&A and data lookup                                  |
| Multi-agent orchestration | **CrewAI** — deferred, not committed                                                              | RAG tool is self-contained and doesn't need it; revisit only if routing between RAG and structured-query tools needs an agent layer   |
| LLM                       | Claude (Sonnet for retrieval routing/tool calls; Sonnet/Opus for the Writer's report generation) | Tier cost: smaller model for simple lookups, larger model for report writing                                                           |
| Embeddings                | Voyage AI or OpenAI `text-embedding-3`                                                           | Open-source bge/e5 is fine too for small doc volumes                                                                                   |
| Vector database           | **Chroma** for MVP (local/lightweight), swap to Qdrant/Pinecone/Weaviate for production          | Don't start with a heavy vector DB                                                                                                     |
| Document parsing/chunking | `unstructured.io` or LlamaIndex loaders                                                          | For PDF/Word product manuals and service terms                                                                                         |
| Structured database       | **PostgreSQL via Supabase** (free tier)                                                           | Replaces local CSV files for products, price list, customers, orders                                                                   |
| Structured queries        | Predefined, parameterized query functions against Postgres                                        | Lookup by customer ID/order number etc. — never let the LLM freely generate SQL against these tables                                  |
| Backend service           | FastAPI exposing query/report endpoints, called by the Next.js frontend                            | Easiest integration path with existing distributor systems                                                                             |
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

**Phase 1 — MVP: single RAG pipeline (done)**

- Build only the product docs + service terms RAG tool, as a self-contained pipeline (no agent wrapper).
- Run Chroma locally to validate ingestion, chunking, and retrieval quality end-to-end.

**Phase 2 — Structured customer/order lookup + frontend**

- Set up a Supabase PostgreSQL project; migrate products, price list, customers, and orders out of local CSV/files into tables.
- Build the structured-query tool: predefined, parameterized query functions only — never LLM-generated SQL against these tables.
- Build the Next.js frontend: question input, answer display with source citations, entry points for the document Q&A and data lookup features.
- Decide routing between the RAG tool and the structured-query tool (plain code vs. an agent layer — see the architecture status note in Section 2).
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

## 6. Future Considerations (not committed, exploratory only)

These are ideas to revisit later, not scheduled into a phase yet:

- **Pre-generation confidence gate**: before calling the LLM to generate an answer, use [Jev](https://typesafe.ai) (TypeSafe AI's typed-decision model) to check whether the retrieved chunks can actually answer the question. Below a confidence threshold (set in code), skip generation and return "not found" directly — cheaper and faster than always calling the LLM.
- **Triage layer in front of the assistant**: use Jev to classify incoming customer messages (category, urgency, sentiment, answerable-by-knowledge-base or not) before they reach RAG. Answerable messages go to RAG as usual; everything else becomes a support ticket stored in Postgres and assigned to a team (sales, warehouse, after-sales, finance, urgent).

## 7. Current Status

Phase 1 (RAG pipeline) is functional: multi-format ingestion (md/docx/pdf), metadata-based routing via `data/metadata.json`, chunking, embedding + storage in Chroma, distance-threshold-filtered retrieval, and a single Claude call for generation — all in `ingest_test.py`. No agent framework wraps it (see architecture status update in Section 2). Next step: Phase 2 — Supabase Postgres for structured data, the structured-query tool, and the Next.js frontend.
