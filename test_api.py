"""Offline tests for the HTTP layer; answer_question is patched, so no network, DB or API cost.

    .venv/bin/python -m unittest test_api -v
"""
import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient

from api import app

client = TestClient(app)


class AskEndpointTests(unittest.TestCase):
    def test_returns_answer_and_tool_names_only(self):
        fake = {
            "answer": "Shipped.",
            "tool_calls": [("get_order", {"order_id": "ORD-1005"})],
            "sources": ["returns_policy.pdf"],
        }
        with patch("api.answer_question", return_value=fake) as mock:
            resp = client.post("/ask", json={"question": "  status of ORD-1005?  "})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"answer": "Shipped.", "tools_used": ["get_order"], "sources": ["returns_policy.pdf"]})
        mock.assert_called_once_with("status of ORD-1005?")

    def test_rejects_empty_and_blank_questions(self):
        with patch("api.answer_question") as mock:
            self.assertEqual(client.post("/ask", json={"question": ""}).status_code, 422)
            self.assertEqual(client.post("/ask", json={"question": "   "}).status_code, 422)
            self.assertEqual(client.post("/ask", json={}).status_code, 422)
        mock.assert_not_called()

    def test_rejects_overlong_question(self):
        with patch("api.answer_question") as mock:
            resp = client.post("/ask", json={"question": "x" * 2001})
        self.assertEqual(resp.status_code, 422)
        mock.assert_not_called()

    def test_failure_returns_502_without_leaking_details(self):
        with patch("api.answer_question", side_effect=RuntimeError("password=hunter2 for Grace Kim")):
            resp = client.post("/ask", json={"question": "anything"})

        self.assertEqual(resp.status_code, 502)
        self.assertNotIn("hunter2", resp.text)
        self.assertNotIn("Grace", resp.text)

    def test_health(self):
        self.assertEqual(client.get("/health").json(), {"status": "ok"})


GRACE = {"customer_id": "CUST-003", "name": "Grace Kim", "email": "grace.kim@example.com",
         "phone": "021 555 0103", "account_type": "retail", "region": "Wellington"}
ORDER = {"order_id": "ORD-1003", "customer_id": "CUST-003", "order_date": date(2026, 7, 1),
         "status": "partially_returned",
         "items": [{"product_code": "SH-203", "product_name": "Twin Shower", "quantity": 1,
                    "unit_price_charged": Decimal("349.00")}]}


class LookupEndpointTests(unittest.TestCase):
    def test_returns_masked_summaries_only(self):
        found = {"type": "name", "customers": [GRACE]}
        with patch("api.search_customers", return_value=found) as mock:
            resp = client.get("/lookup", params={"q": "  Grace Kim "})

        self.assertEqual(resp.status_code, 200)
        mock.assert_called_once_with("Grace Kim")
        self.assertEqual(resp.json(), {"type": "name", "customers": [{
            "customer_id": "CUST-003", "name": "Grace Kim", "account_type": "retail",
            "region": "Wellington", "email_masked": "g***@example.com", "phone_masked": "*** *** 0103",
        }]})
        self.assertNotIn("grace.kim@example.com", resp.text)
        self.assertNotIn("555 0103", resp.text.replace("*** *** 0103", ""))

    def test_no_match_is_an_empty_list_not_an_error(self):
        with patch("api.search_customers", return_value={"type": "email", "customers": []}):
            resp = client.get("/lookup", params={"q": "nobody@example.com"})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"type": "email", "customers": []})

    def test_rejects_missing_blank_and_overlong_search(self):
        with patch("api.search_customers") as mock:
            self.assertEqual(client.get("/lookup").status_code, 422)
            self.assertEqual(client.get("/lookup", params={"q": ""}).status_code, 422)
            self.assertEqual(client.get("/lookup", params={"q": "   "}).status_code, 422)
            self.assertEqual(client.get("/lookup", params={"q": "x" * 201}).status_code, 422)
        mock.assert_not_called()

    def test_failure_returns_502_without_leaking_details(self):
        with patch("api.search_customers", side_effect=RuntimeError("Grace Kim grace.kim@example.com")):
            resp = client.get("/lookup", params={"q": "Grace Kim"})

        self.assertEqual(resp.status_code, 502)
        self.assertNotIn("Grace", resp.text)
        self.assertNotIn("example.com", resp.text)


class CustomerDetailEndpointTests(unittest.TestCase):
    def test_returns_customer_and_orders_with_exact_prices(self):
        with patch("api.get_customer", return_value=GRACE), \
             patch("api.get_orders_for_customer", return_value=[ORDER]) as orders:
            resp = client.get("/lookup/customers/CUST-003")

        self.assertEqual(resp.status_code, 200)
        orders.assert_called_once_with("CUST-003")
        body = resp.json()
        self.assertEqual(body["customer"], GRACE)
        self.assertEqual(body["orders"][0]["order_date"], "2026-07-01")
        self.assertEqual(body["orders"][0]["items"][0]["unit_price_charged"], "349.00")

    def test_unknown_customer_is_404_and_skips_orders(self):
        with patch("api.get_customer", return_value=None), patch("api.get_orders_for_customer") as orders:
            resp = client.get("/lookup/customers/CUST-999")

        self.assertEqual(resp.status_code, 404)
        orders.assert_not_called()

    def test_malformed_id_is_rejected_before_any_query(self):
        with patch("api.get_customer") as mock:
            for bad in ("grace", "CUST-", "CUST-1;drop", "ORD-1003"):
                self.assertEqual(client.get(f"/lookup/customers/{bad}").status_code, 422, bad)
        mock.assert_not_called()

    def test_failure_returns_502_without_leaking_details(self):
        with patch("api.get_customer", side_effect=RuntimeError("secret Grace Kim")):
            resp = client.get("/lookup/customers/CUST-003")

        self.assertEqual(resp.status_code, 502)
        self.assertNotIn("Grace", resp.text)


if __name__ == "__main__":
    unittest.main()
