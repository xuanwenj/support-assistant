"""Search behind the /lookup box: work out what the staff member typed, call the matching query.

Classification is plain code (no LLM), so it is exact, free and never sends names, emails or
phone numbers to a cloud API. Every kind of input ends up as a list of customers.
"""
import re

from queries import (
    get_customer,
    get_customer_by_email,
    get_customer_by_phone,
    get_customers_by_name,
    get_order,
)

MIN_PHONE_DIGITS = 6


def classify_query(text):
    """Return (kind, value). kind is order_id, customer_id, email, phone, name or empty."""
    text = (text or "").strip()
    if not text:
        return "empty", ""
    if re.fullmatch(r"ORD-\d+", text, re.IGNORECASE):
        return "order_id", text.upper()
    if re.fullmatch(r"CUST-\d+", text, re.IGNORECASE):
        return "customer_id", text.upper()
    if "@" in text:
        return "email", text
    if re.fullmatch(r"[\d\s+\-()]+", text) and len(re.sub(r"\D", "", text)) >= MIN_PHONE_DIGITS:
        return "phone", text
    return "name", text


def search_customers(text):
    """Return {"type": kind, "customers": [full customer dicts]}; an order ID resolves to its customer."""
    kind, value = classify_query(text)

    if kind == "order_id":
        order = get_order(value)
        customer = get_customer(order["customer_id"]) if order else None
        customers = [customer] if customer else []
    elif kind == "customer_id":
        customer = get_customer(value)
        customers = [customer] if customer else []
    elif kind == "email":
        customer = get_customer_by_email(value)
        customers = [customer] if customer else []
    elif kind == "phone":
        customers = get_customer_by_phone(value)
    elif kind == "name":
        customers = get_customers_by_name(value)
    else:
        customers = []

    return {"type": kind, "customers": customers}


def mask_email(email):
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


def mask_phone(phone):
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    return f"*** *** {digits[-4:]}" if len(digits) >= 4 else "***"


def customer_summary(customer):
    """What the pick-list shows: enough to tell customers apart, without full contact details."""
    return {
        "customer_id": customer["customer_id"],
        "name": customer["name"],
        "account_type": customer["account_type"],
        "region": customer["region"],
        "email_masked": mask_email(customer["email"]),
        "phone_masked": mask_phone(customer["phone"]),
    }
