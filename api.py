"""HTTP layer over the router, called by the Next.js route handler (not by the browser).

Run:  .venv/bin/python -m uvicorn api:app --host 127.0.0.1 --port 8000

No CORS middleware on purpose: only the Next.js server calls this, so the browser
never needs cross-origin access. Questions and answers are not logged (they can
contain customer names and order details).
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import FastAPI, HTTPException, Path, Query
from pydantic import BaseModel, Field

from queries import get_customer, get_orders_for_customer
from router import answer_question
from search import customer_summary, search_customers

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


class CustomerSummary(BaseModel):
    customer_id: str
    name: str
    account_type: str
    region: Optional[str]
    email_masked: str
    phone_masked: Optional[str]


class LookupResponse(BaseModel):
    type: str
    customers: list[CustomerSummary]


class Customer(BaseModel):
    customer_id: str
    name: str
    email: str
    phone: Optional[str]
    account_type: str
    region: Optional[str]


class OrderItem(BaseModel):
    product_code: str
    product_name: str
    quantity: int
    unit_price_charged: Decimal


class Order(BaseModel):
    order_id: str
    customer_id: str
    order_date: date
    status: str
    items: list[OrderItem]


class CustomerDetail(BaseModel):
    customer: Customer
    orders: list[Order]


@app.get("/lookup", response_model=LookupResponse)
def lookup(q: str = Query(min_length=1, max_length=200)):
    """Find customers by order ID, customer ID, email, phone or name; the query is never logged."""
    q = q.strip()
    if not q:
        raise HTTPException(status_code=422, detail="Search must not be blank.")

    try:
        result = search_customers(q)
    except Exception:
        # Don't echo exception text: it can include query details.
        raise HTTPException(status_code=502, detail="The lookup failed. Try again.")

    return LookupResponse(
        type=result["type"],
        customers=[customer_summary(c) for c in result["customers"]],
    )


@app.get("/lookup/customers/{customer_id}", response_model=CustomerDetail)
def lookup_customer(customer_id: str = Path(pattern=r"^CUST-\d+$", max_length=32)):
    """Full details and orders for one customer, used when a person is picked from the list."""
    try:
        customer = get_customer(customer_id)
        orders = get_orders_for_customer(customer_id) if customer else []
    except Exception:
        raise HTTPException(status_code=502, detail="The lookup failed. Try again.")

    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found.")
    return CustomerDetail(customer=customer, orders=orders)


@app.get("/health")
def health():
    return {"status": "ok"}
