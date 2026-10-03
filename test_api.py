"""Offline tests for the HTTP layer; answer_question is patched, so no network, DB or API cost.

    .venv/bin/python -m unittest test_api -v
"""
import unittest
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


if __name__ == "__main__":
    unittest.main()
