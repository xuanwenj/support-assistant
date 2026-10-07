"""Tests for the tool-use loop.

Offline tests (default) use a scripted fake client, so they cost nothing and need no network.
Live tests hit Supabase, Chroma and the Claude API. Run them with:

    RUN_LIVE_TESTS=1 .venv/bin/python -m unittest test_router -v

Live tests assume `python ingest.py` has been run and the seed data is loaded.
"""
import itertools
import json
import os
import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import router
from tools import TOOL_FUNCTIONS, TOOL_SCHEMAS, run_tool

LIVE = os.getenv("RUN_LIVE_TESTS") == "1"


class FakeClient:
    def __init__(self, responses):
        self._responses = iter(responses)
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        # Snapshot messages: the loop keeps appending to the same list.
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return next(self._responses)


def text_response(text):
    return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)])


def tool_response(*calls):
    blocks = [
        SimpleNamespace(type="tool_use", id=call_id, name=name, input=tool_input)
        for call_id, name, tool_input in calls
    ]
    return SimpleNamespace(stop_reason="tool_use", content=blocks)


class ToolTests(unittest.TestCase):
    def test_schemas_match_dispatch_map(self):
        self.assertEqual({s["name"] for s in TOOL_SCHEMAS}, set(TOOL_FUNCTIONS))
        for schema in TOOL_SCHEMAS:
            spec = schema["input_schema"]
            self.assertTrue(set(spec["required"]) <= set(spec["properties"]))

    def test_decimal_and_date_are_serialized(self):
        row = {"price": Decimal("349.00"), "order_date": date(2026, 7, 1)}
        with patch.dict(TOOL_FUNCTIONS, {"get_order": lambda order_id: row}):
            content, is_error = run_tool("get_order", {"order_id": "ORD-1003"})

        self.assertFalse(is_error)
        self.assertEqual(json.loads(content), {"price": "349.00", "order_date": "2026-07-01"})

    def test_not_found_results_serialize(self):
        with patch.dict(TOOL_FUNCTIONS, {"get_order": lambda order_id: None,
                                         "get_orders_by_username": lambda username: []}):
            self.assertEqual(run_tool("get_order", {"order_id": "x"}), ("null", False))
            self.assertEqual(run_tool("get_orders_by_username", {"username": "x"}), ("[]", False))

    def test_customer_lookup_tools_are_registered(self):
        names = {s["name"] for s in TOOL_SCHEMAS}
        self.assertTrue({"get_customer", "get_customer_by_email", "get_customer_by_phone",
                         "get_orders_for_customer"} <= names)

    def test_customer_not_found_results_serialize(self):
        with patch.dict(TOOL_FUNCTIONS, {"get_customer": lambda customer_id: None,
                                         "get_customer_by_email": lambda email: None,
                                         "get_customer_by_phone": lambda phone: [],
                                         "get_orders_for_customer": lambda customer_id: []}):
            self.assertEqual(run_tool("get_customer", {"customer_id": "x"}), ("null", False))
            self.assertEqual(run_tool("get_customer_by_email", {"email": "x"}), ("null", False))
            self.assertEqual(run_tool("get_customer_by_phone", {"phone": "x"}), ("[]", False))
            self.assertEqual(run_tool("get_orders_for_customer", {"customer_id": "x"}), ("[]", False))

    def test_unknown_tool_is_an_error_result(self):
        content, is_error = run_tool("drop_all_tables", {})
        self.assertTrue(is_error)
        self.assertIn("Unknown tool", content)

    def test_tool_exception_becomes_error_result_without_details(self):
        def boom(order_id):
            raise RuntimeError("password=hunter2")

        with patch.dict(TOOL_FUNCTIONS, {"get_order": boom}):
            content, is_error = run_tool("get_order", {"order_id": "ORD-1"})

        self.assertTrue(is_error)
        self.assertNotIn("hunter2", content)


class LoopMechanicsTests(unittest.TestCase):
    def test_answers_directly_when_no_tool_is_needed(self):
        client = FakeClient([text_response("Hello")])

        result = router.answer_question("hi", client=client)

        self.assertEqual(result, {"answer": "Hello", "tool_calls": [], "sources": []})
        self.assertEqual(len(client.calls), 1)
        self.assertEqual({t["name"] for t in client.calls[0]["tools"]}, set(TOOL_FUNCTIONS))

    def test_tool_result_is_fed_back_with_matching_id(self):
        first = tool_response(("toolu_1", "get_order", {"order_id": "ORD-1005"}))
        client = FakeClient([first, text_response("It is pending.")])
        fake_order = {"status": "pending", "order_date": date(2026, 9, 18)}

        with patch.dict(TOOL_FUNCTIONS, {"get_order": lambda order_id: fake_order}):
            result = router.answer_question("status of ORD-1005?", client=client)

        self.assertEqual(result["answer"], "It is pending.")
        self.assertEqual(result["tool_calls"], [("get_order", {"order_id": "ORD-1005"})])

        second_call_messages = client.calls[1]["messages"]
        self.assertEqual([m["role"] for m in second_call_messages], ["user", "assistant", "user"])
        self.assertEqual(second_call_messages[1]["content"], first.content)
        tool_result = second_call_messages[2]["content"][0]
        self.assertEqual(tool_result["type"], "tool_result")
        self.assertEqual(tool_result["tool_use_id"], "toolu_1")
        self.assertEqual(json.loads(tool_result["content"])["order_date"], "2026-09-18")
        self.assertFalse(tool_result["is_error"])

    def test_parallel_tool_calls_return_in_one_user_message(self):
        first = tool_response(
            ("toolu_a", "get_product", {"product_code": "PC-101"}),
            ("toolu_b", "get_product", {"product_code": "PC-102"}),
        )
        client = FakeClient([first, text_response("done")])

        with patch.dict(TOOL_FUNCTIONS, {"get_product": lambda product_code: {"code": product_code}}):
            router.answer_question("compare PC-101 and PC-102", client=client)

        results_message = client.calls[1]["messages"][2]
        self.assertEqual([r["tool_use_id"] for r in results_message["content"]], ["toolu_a", "toolu_b"])

    def test_chains_tools_across_rounds(self):
        client = FakeClient([
            tool_response(("t1", "get_orders_by_username", {"username": "Grace Kim"})),
            tool_response(("t2", "search_documents", {"question": "bundle return pricing"})),
            text_response("Priced correctly."),
        ])

        with patch.dict(TOOL_FUNCTIONS, {"get_orders_by_username": lambda username: [],
                                         "search_documents": lambda question: []}):
            result = router.answer_question("was the return priced right?", client=client)

        self.assertEqual([name for name, _ in result["tool_calls"]],
                         ["get_orders_by_username", "search_documents"])
        self.assertEqual(len(client.calls), 3)
        self.assertEqual(len(client.calls[2]["messages"]), 5)

    def test_sources_are_collected_from_document_search_only(self):
        client = FakeClient([
            tool_response(("t1", "search_documents", {"question": "returns"}),
                          ("t2", "get_product", {"product_code": "PC-101"})),
            tool_response(("t3", "search_documents", {"question": "warranty"})),
            text_response("See policy."),
        ])
        passages = {
            "returns": [{"text": "a", "source_file": "returns_policy.pdf", "distance": 0.5},
                        {"text": "b", "source_file": "faq.md", "distance": 0.7}],
            "warranty": [{"text": "c", "source_file": "returns_policy.pdf", "distance": 0.6}],
        }

        with patch.dict(TOOL_FUNCTIONS, {"search_documents": lambda question: passages[question],
                                         "get_product": lambda product_code: {"source_file": "not_a_doc"}}):
            result = router.answer_question("policy?", client=client)

        self.assertEqual(result["sources"], ["returns_policy.pdf", "faq.md"])

    def test_no_sources_when_search_finds_nothing_or_fails(self):
        client = FakeClient([
            tool_response(("t1", "search_documents", {"question": "x"})),
            tool_response(("t2", "search_documents", {"question": "y"})),
            text_response("Nothing found."),
        ])

        def search(question):
            if question == "y":
                raise RuntimeError("chroma down")
            return []

        with patch.dict(TOOL_FUNCTIONS, {"search_documents": search}):
            result = router.answer_question("policy?", client=client)

        self.assertEqual(result["sources"], [])

    def test_tool_error_is_reported_to_the_model_and_loop_continues(self):
        client = FakeClient([
            tool_response(("t1", "get_order", {"order_id": "ORD-1"})),
            text_response("Sorry, the lookup failed."),
        ])

        def boom(order_id):
            raise RuntimeError("db down")

        with patch.dict(TOOL_FUNCTIONS, {"get_order": boom}):
            result = router.answer_question("status?", client=client)

        self.assertEqual(result["answer"], "Sorry, the lookup failed.")
        self.assertTrue(client.calls[1]["messages"][2]["content"][0]["is_error"])

    def test_iteration_cap_stops_a_runaway_loop(self):
        looping = tool_response(("t1", "get_order", {"order_id": "ORD-1"}))
        client = FakeClient(itertools.repeat(looping))

        with patch.dict(TOOL_FUNCTIONS, {"get_order": lambda order_id: None}):
            result = router.answer_question("loop forever", client=client, max_iterations=3)

        self.assertEqual(len(client.calls), 3)
        self.assertEqual(len(result["tool_calls"]), 3)
        self.assertIn("Stopped after 3", result["answer"])

    def test_refusal_is_returned_not_crashed_on(self):
        client = FakeClient([SimpleNamespace(stop_reason="refusal", content=[])])

        result = router.answer_question("...", client=client)

        self.assertIn("declined", result["answer"])


@unittest.skipUnless(LIVE, "set RUN_LIVE_TESTS=1 to hit Supabase")
class LiveDatabaseTests(unittest.TestCase):
    def test_real_order_serializes_and_keeps_bundle_prices(self):
        content, is_error = run_tool("get_order", {"order_id": "ORD-1003"})

        self.assertFalse(is_error)
        order = json.loads(content)
        self.assertEqual(order["order_date"], "2026-07-01")
        prices = {item["product_code"]: item["unit_price_charged"] for item in order["items"]}
        self.assertEqual(prices, {"SH-203": "349.00", "PC-110": "49.00"})


@unittest.skipUnless(LIVE, "set RUN_LIVE_TESTS=1 to call the Claude API")
class LiveRouterTests(unittest.TestCase):
    def tools_used(self, result):
        return [name for name, _ in result["tool_calls"]]

    def test_order_status_uses_the_order_tool(self):
        result = router.answer_question("What's the status of order ORD-1005?")

        self.assertIn("get_order", self.tools_used(result))
        self.assertIn("pending", result["answer"].lower())

    def test_unknown_order_is_reported_as_not_found(self):
        result = router.answer_question("What's the status of order ORD-9999?")

        self.assertIn("get_order", self.tools_used(result))
        phrases = ["not found", "couldn't find", "could not find", "no order",
                   "doesn't exist", "does not exist", "unable to find", "no record"]
        self.assertTrue(any(p in result["answer"].lower() for p in phrases))

    def test_policy_question_uses_documents_and_no_database(self):
        result = router.answer_question("Is a dripping tap covered by warranty?")

        used = self.tools_used(result)
        self.assertIn("search_documents", used)
        self.assertFalse({"get_order", "get_orders_by_username"} & set(used))

    def test_compound_question_uses_both_sources(self):
        result = router.answer_question(
            "Grace Kim returned part of her twin shower bundle. Look up her order, and check our "
            "policy on partial bundle returns: was the return priced the way the policy says?"
        )

        used = self.tools_used(result)
        self.assertIn("get_orders_by_username", used)
        self.assertIn("search_documents", used)

    def test_orders_by_email_use_a_customer_tool(self):
        result = router.answer_question("What has grace.kim.dunedin@example.com ordered?")

        used = self.tools_used(result)
        self.assertTrue({"get_customer_by_email", "get_orders_for_customer"} & set(used))
        self.assertIn("ORD-1006", result["answer"])
        self.assertNotIn("ORD-1003", result["answer"])

    def test_orders_by_phone_use_the_phone_tool(self):
        result = router.answer_question("Show me the orders for the customer with phone +64 21 555 0103.")

        self.assertIn("get_customer_by_phone", self.tools_used(result))
        self.assertIn("ORD-1003", result["answer"])
        self.assertNotIn("ORD-1006", result["answer"])

    def test_shared_name_asks_which_customer(self):
        result = router.answer_question("Show me the orders for Grace Kim.")

        answer = result["answer"].lower()
        self.assertIn("get_orders_by_username", self.tools_used(result))
        self.assertTrue("cust-003" in answer and "cust-006" in answer)
        self.assertTrue(any(w in answer for w in ("which", "several", "multiple", "two customers", "email", "phone")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
