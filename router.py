import json

import anthropic
from dotenv import load_dotenv
load_dotenv()

from tools import TOOL_SCHEMAS, run_tool

MODEL = "claude-haiku-4-5"
MAX_ITERATIONS = 5

SYSTEM_PROMPT = """You are a support assistant for a plumbing-fixtures distributor. Your users are internal sales and customer-service staff.

Answer using only what the tools return - never guess order details, prices, warranty terms or policy from general knowledge.
- Orders, customers and product specs come from the database tools.
- Customer names are not unique. If a name lookup returns orders with more than one customer_id, do not merge them: say there are several customers with that name and ask for an email, phone number or customer ID.
- Policy, how-to and troubleshooting answers come from search_documents. Mention the source file for anything you take from it.
- Some questions need both (for example, checking whether an order was handled according to policy) - call as many tools as you need.
- If a tool returns null or an empty list, or the documents don't cover the question, say so plainly instead of filling the gap."""


def _final_text(response):
    return "".join(block.text for block in response.content if block.type == "text")


def _add_sources(sources, tool_name, content):
    """Record the source files of retrieved passages, in order, without duplicates."""
    if tool_name != "search_documents":
        return
    for passage in json.loads(content):
        if passage["source_file"] not in sources:
            sources.append(passage["source_file"])


def answer_question(question, client=None, max_iterations=MAX_ITERATIONS):
    client = client or anthropic.Anthropic()
    messages = [{"role": "user", "content": question}]
    tool_calls = []
    sources = []

    for _ in range(max_iterations):
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )

        if response.stop_reason == "refusal":
            return {"answer": "The request was declined by the model's safety policy.", "tool_calls": tool_calls, "sources": sources}
        if response.stop_reason != "tool_use":
            return {"answer": _final_text(response), "tool_calls": tool_calls, "sources": sources}

        # Echo the full content back (not just text) so any thinking blocks stay intact.
        messages.append({"role": "assistant", "content": response.content})

        # All results for one assistant turn go back in a single user message.
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            tool_calls.append((block.name, block.input))
            content, is_error = run_tool(block.name, block.input)
            if not is_error:
                _add_sources(sources, block.name, content)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
                "is_error": is_error,
            })
        messages.append({"role": "user", "content": tool_results})

    return {
        "answer": f"Stopped after {max_iterations} tool rounds without reaching an answer.",
        "tool_calls": tool_calls,
        "sources": sources,
    }


if __name__ == "__main__":
    result = answer_question("What's the status of order ORD-1005?")
    print(result["answer"])
    print("tools used:", [name for name, _ in result["tool_calls"]])
    print("sources:", result["sources"])
