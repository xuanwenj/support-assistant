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
Retrieval — given a user's question, embed the question the same way, ask Chroma for the top-k most similar chunks.
**Augmentation + generation** — stuff those retrieved chunks into a prompt alongside the user's question, send it to Claude via the anthropic SDK, get back an answer grounded in your docs.

## Problems

**Irrelevant chunk retrieved due to non-content paragraph in FAQ doc**
Context: Testing retrieval with n_results=3 against customer-faq.md.

Problem: The 3rd result returned was the FAQ file's intro paragrap ("Collected from common customer questions...") — not an actual Q&A pair. It shares surface-level vocabulary with the query but isn't semantically relevant content.

Root Cause: Chunking splits on `---`, which treats the intro paragraph as its own standalone chunk — same status as any real Q&A pair, even though it's metadata/description text, not answerable content. n_results=3 also forces exactly 3 results regardless of whether a 3rd relevant match exists.

Solution: Filter out non-content paragraphs before chunking (e.g. skip segments
without a "Q:" marker)

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
