import json
from functools import lru_cache

import chromadb

from queries import (
    get_customer,
    get_customer_by_email,
    get_customer_by_phone,
    get_order,
    get_orders_by_username,
    get_orders_for_customer,
    get_product,
)
from retrieval import retrieve_relevant_chunks


@lru_cache(maxsize=1)
def _get_collection():
    client = chromadb.PersistentClient(path="./chroma_data")
    return client.get_or_create_collection("knowledge_base")


def search_documents(question):
    chunks = retrieve_relevant_chunks(_get_collection(), question)
    return [
        {
            "text": chunk["text"],
            "source_file": chunk["metadata"]["source_file"],
            "distance": chunk["distance"],
        }
        for chunk in chunks
    ]


TOOL_SCHEMAS = [
    {
        "name": "get_order",
        "description": (
            "Look up one order by its exact order ID (format ORD-1234). Returns the order "
            "status, date, customer ID, and every line item with product name, quantity, "
            "and the unit price actually charged (which can be below the product's normal "
            "price, e.g. bundle pricing). Returns null if no such order exists. Use this "
            "when the question names a specific order ID."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Exact order ID, e.g. ORD-1003."},
            },
            "required": ["order_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_orders_by_username",
        "description": (
            "Find all orders belonging to customers whose full name exactly matches the "
            "given name (case-sensitive), each with its line items. The 'username' is the "
            "customer's name as stored in the customers table, e.g. 'Grace Kim'. Names are "
            "not unique, so this can return orders from several different customers - check "
            "customer_id on each order. Returns an empty list if no customer matches. Use "
            "this when the question identifies a customer by name instead of an order ID."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Customer's full name, e.g. Grace Kim."},
            },
            "required": ["username"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_product",
        "description": (
            "Look up one product by its exact product code (e.g. PC-101, SH-203). Returns "
            "name, category, type, material, min/max operating pressure in kPa, warranty "
            "terms, and retail and trade prices in NZD. Returns null if the code does not "
            "exist. Use this for exact specs, prices, or warranty terms of a known product."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_code": {"type": "string", "description": "Exact product code, e.g. PC-101."},
            },
            "required": ["product_code"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_customer",
        "description": (
            "Look up one customer by exact customer ID (format CUST-001). Returns customer ID, "
            "name, email, phone (may be null), account type ('retail' or 'trade') and region. "
            "Returns null if no such customer exists. Use this when the question gives a "
            "customer ID, or to get contact details for the customer_id on an order."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Exact customer ID, e.g. CUST-003."},
            },
            "required": ["customer_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_customer_by_email",
        "description": (
            "Look up one customer by email address (case-insensitive exact match). Emails are "
            "unique, so this returns a single customer (same fields as get_customer) or null "
            "if no customer has that email. Use this when the question gives an email address."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "Full email address, e.g. grace.kim@example.com."},
            },
            "required": ["email"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_customer_by_phone",
        "description": (
            "Find customers by phone number. Spacing, dashes and a +64 country code are "
            "ignored, so '021 555 0103' and '+6421 555 0103' match the same customer. Phone "
            "numbers are not unique, so this returns a list of customers (same fields as "
            "get_customer), which is empty if nothing matches. If it returns several "
            "customers, do not guess which one is meant. Use this when the question gives "
            "a phone number."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "phone": {"type": "string", "description": "Phone number in any common format, e.g. 021 555 0103."},
            },
            "required": ["phone"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_orders_for_customer",
        "description": (
            "List all orders for one customer by exact customer ID (format CUST-001), oldest "
            "first, each with its line items (product name, quantity, unit price actually "
            "charged). Returns an empty list if the customer has no orders or does not exist. "
            "Use this once you know the customer ID, for example after get_customer_by_email "
            "or get_customer_by_phone, or when it is the only way to tell apart customers "
            "who share a name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Exact customer ID, e.g. CUST-003."},
            },
            "required": ["customer_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_documents",
        "description": (
            "Semantic search over the company's written documents: customer FAQ, installation "
            "guides, returns and warranty policy, staff troubleshooting notes, product "
            "catalog, supplier bulletins. Returns the most relevant passages with their "
            "source file, or an empty list if nothing relevant exists. Use this for policy, "
            "how-to, and troubleshooting questions - anything answered by prose rather than "
            "by a database record. Do not use it to look up orders or customers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "A self-contained search query describing the information needed.",
                },
            },
            "required": ["question"],
            "additionalProperties": False,
        },
    },
]

TOOL_FUNCTIONS = {
    "get_order": get_order,
    "get_orders_by_username": get_orders_by_username,
    "get_product": get_product,
    "get_customer": get_customer,
    "get_customer_by_email": get_customer_by_email,
    "get_customer_by_phone": get_customer_by_phone,
    "get_orders_for_customer": get_orders_for_customer,
    "search_documents": search_documents,
}


def run_tool(name, tool_input):
    """Run a tool and return (content, is_error) ready for a tool_result block."""
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return f"Unknown tool: {name}", True

    try:
        result = func(**tool_input)
    except Exception as exc:
        return f"Tool {name} failed: {type(exc).__name__}", True

    # Query results contain Decimal and datetime.date, which json can't encode natively.
    return json.dumps(result, default=str), False
