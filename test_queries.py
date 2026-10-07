"""Tests for the lookup functions in queries.py.

The normalization tests are offline. The database tests hit Supabase; run them with:

    RUN_LIVE_TESTS=1 .venv/bin/python -m unittest test_queries -v

Live tests assume the seed data plus seed_test_data.sql (a second "Grace Kim", CUST-006).
"""
import os
import unittest

import queries

LIVE = os.getenv("RUN_LIVE_TESTS") == "1"


class NormalizePhoneTests(unittest.TestCase):
    def test_formats_collapse_to_the_same_digits(self):
        for raw in ("021 555 0103", "0215550103", "+64 21 555 0103", "+6421-555-0103", "(021) 555-0103"):
            self.assertEqual(queries._normalize_phone(raw), "0215550103", raw)

    def test_empty_and_non_numeric_become_empty(self):
        for raw in ("", "   ", "abc", None):
            self.assertEqual(queries._normalize_phone(raw), "", raw)


@unittest.skipUnless(LIVE, "set RUN_LIVE_TESTS=1 to hit Supabase")
class LiveQueryTests(unittest.TestCase):
    def test_get_customer(self):
        customer = queries.get_customer("CUST-003")

        self.assertEqual(customer["name"], "Grace Kim")
        self.assertEqual(
            set(customer),
            {"customer_id", "name", "email", "phone", "account_type", "region"},
        )

    def test_get_customer_unknown_is_none(self):
        self.assertIsNone(queries.get_customer("CUST-999"))

    def test_get_customer_by_email_ignores_case_and_padding(self):
        customer = queries.get_customer_by_email("  GRACE.KIM@example.com ")

        self.assertEqual(customer["customer_id"], "CUST-003")

    def test_get_customer_by_email_unknown_is_none(self):
        self.assertIsNone(queries.get_customer_by_email("nobody@example.com"))

    def test_get_customer_by_phone_matches_any_format(self):
        for raw in ("021 555 0103", "0215550103", "+64 21 555 0103"):
            ids = [c["customer_id"] for c in queries.get_customer_by_phone(raw)]
            self.assertEqual(ids, ["CUST-003"], raw)

    def test_get_customer_by_phone_no_match_or_blank_is_empty(self):
        for raw in ("021 555 9999", "", "abc"):
            self.assertEqual(queries.get_customer_by_phone(raw), [], raw)

    def test_get_customers_by_name_is_case_insensitive_and_returns_all(self):
        for raw in ("Grace Kim", "grace kim", "  GRACE KIM "):
            ids = [c["customer_id"] for c in queries.get_customers_by_name(raw)]
            self.assertEqual(ids, ["CUST-003", "CUST-006"], raw)

    def test_get_customers_by_name_is_exact_not_partial(self):
        self.assertEqual(queries.get_customers_by_name("Grace"), [])
        self.assertEqual(queries.get_customers_by_name("Nobody Here"), [])

    def test_get_orders_for_customer_includes_items(self):
        orders = queries.get_orders_for_customer("CUST-003")

        self.assertEqual([o["order_id"] for o in orders], ["ORD-1003"])
        prices = {i["product_code"]: str(i["unit_price_charged"]) for i in orders[0]["items"]}
        self.assertEqual(prices, {"SH-203": "349.00", "PC-110": "49.00"})

    def test_get_orders_for_customer_unknown_is_empty(self):
        self.assertEqual(queries.get_orders_for_customer("CUST-999"), [])

    def test_order_without_items_gets_an_empty_list(self):
        orders = [{"order_id": "ORD-X"}]

        class Cur:
            def execute(self, *args):
                pass

            def fetchall(self):
                return []

        self.assertEqual(queries._attach_items(Cur(), orders), [{"order_id": "ORD-X", "items": []}])

    def test_shared_name_returns_orders_from_both_customers(self):
        orders = queries.get_orders_by_username("Grace Kim")

        self.assertEqual({o["customer_id"] for o in orders}, {"CUST-003", "CUST-006"})
        by_customer = {o["customer_id"]: o for o in orders}
        self.assertEqual(len(by_customer["CUST-003"]["items"]), 2)
        self.assertEqual(len(by_customer["CUST-006"]["items"]), 1)

    def test_duplicate_name_customers_are_told_apart_by_email(self):
        customer = queries.get_customer_by_email("grace.kim.dunedin@example.com")

        self.assertEqual(customer["customer_id"], "CUST-006")
        self.assertEqual([o["order_id"] for o in queries.get_orders_for_customer("CUST-006")], ["ORD-1006"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
