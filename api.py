"""HTTP layer over the router, called by the Next.js route handler (not by the browser).

Run:  .venv/bin/python -m uvicorn api:app --host 127.0.0.1 --port 8000

No CORS middleware on purpose: only the Next.js server calls this, so the browser
never needs cross-origin access. Questions and answers are not logged (they can
contain customer names and order details).
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from router import answer_question

app = FastAPI(title="Support Assistant API")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class AskResponse(BaseModel):
    answer: str
    tools_used: list[str]
    sources: list[str]


@app.post("/ask", response_model=AskResponse)
def ask(body: AskRequest):
    # Plain `def` so FastAPI runs this blocking call in a worker thread.
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be blank.")

    try:
        result = answer_question(question)
    except Exception:
        # Don't echo exception text: it can include query details.
        raise HTTPException(status_code=502, detail="The assistant failed to answer. Try again.")

    # Tool names only; tool inputs hold customer names and order IDs.
    return AskResponse(
        answer=result["answer"],
        tools_used=[name for name, _ in result["tool_calls"]],
        sources=result["sources"],
    )


@app.get("/health")
def health():
    return {"status": "ok"}
