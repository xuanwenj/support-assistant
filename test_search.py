"""Tests for search.py (the /lookup box logic).

Classification, masking and dispatch are offline. The database tests hit Supabase; run them with:

    RUN_LIVE_TESTS=1 .venv/bin/python -m unittest test_search -v

Live tests assume the seed data plus seed_test_data.sql (a second "Grace Kim", CUST-006).
"""
import os
import unittest
from unittest.mock import patch

import search

LIVE = os.getenv("RUN_LIVE_TESTS") == "1"

GRACE = {"customer_id": "CUST-003", "name": "Grace Kim", "email": "grace.kim@example.com",
         "phone": "021 555 0103", "account_type": "retail", "region": "Wellington"}


class ClassifyQueryTests(unittest.TestCase):
    def test_each_kind_of_input(self):
        cases = {
            "ORD-1003": ("order_id", "ORD-1003"),
            "  ord-1003 ": ("order_id", "ORD-1003"),
            "CUST-003": ("customer_id", "CUST-003"),
            "cust-3": ("customer_id", "CUST-3"),
            "grace.kim@example.com": ("email", "grace.kim@example.com"),
            "021 555 0103": ("phone", "021 555 0103"),
            "+64 21 555 0103": ("phone", "+64 21 555 0103"),
            "(021) 555-0103": ("phone", "(021) 555-0103"),
            "Grace Kim": ("name", "Grace Kim"),
            "  Grace   Kim ": ("name", "Grace   Kim"),
        }
        for text, expected in cases.items():
            self.assertEqual(search.classify_query(text), expected, text)

    def test_blank_input_is_empty(self):
        for text in ("", "   ", None):
            self.assertEqual(search.classify_query(text)[0], "empty", text)

    def test_ids_that_are_not_ids_fall_through_to_name(self):
        for text in ("ORD-", "ORD-12A", "CUST", "CUST-00X", "ORD 1003"):
            self.assertEqual(search.classify_query(text)[0], "name", text)

    def test_short_digit_strings_are_not_phones(self):
        self.assertEqual(search.classify_query("1003")[0], "name")


class MaskingTests(unittest.TestCase):
    def test_summary_hides_full_contact_details(self):
        summary = search.customer_summary(GRACE)

        self.assertEqual(summary["email_masked"], "g***@example.com")
        self.assertEqual(summary["phone_masked"], "*** *** 0103")
        self.assertNotIn("email", summary)
        self.assertNotIn("phone", summary)

    def test_missing_phone_stays_none(self):
        self.assertIsNone(search.customer_summary({**GRACE, "phone": None})["phone_masked"])


class SearchDispatchTests(unittest.TestCase):
    def test_order_id_resolves_to_its_customer(self):
        with patch("search.get_order", return_value={"order_id": "ORD-1003", "customer_id": "CUST-003"}), \
             patch("search.get_customer", return_value=GRACE) as get_customer:
            result = search.search_customers("ord-1003")

        self.assertEqual(result, {"type": "order_id", "customers": [GRACE]})
        get_customer.assert_called_once_with("CUST-003")

    def test_unknown_order_and_customer_give_no_customers(self):
        with patch("search.get_order", return_value=None):
            self.assertEqual(search.search_customers("ORD-9999"), {"type": "order_id", "customers": []})
        with patch("search.get_customer", return_value=None):
            self.assertEqual(search.search_customers("CUST-999"), {"type": "customer_id", "customers": []})

    def test_email_phone_and_name_use_their_own_lookup(self):
        with patch("search.get_customer_by_email", return_value=GRACE) as by_email:
            self.assertEqual(search.search_customers("a@b.co")["customers"], [GRACE])
            by_email.assert_called_once_with("a@b.co")
        with patch("search.get_customer_by_phone", return_value=[GRACE, GRACE]) as by_phone:
            self.assertEqual(len(search.search_customers("021 555 0103")["customers"]), 2)
            by_phone.assert_called_once_with("021 555 0103")
        with patch("search.get_customers_by_name", return_value=[]) as by_name:
            self.assertEqual(search.search_customers("Nobody"), {"type": "name", "customers": []})
            by_name.assert_called_once_with("Nobody")

    def test_blank_search_touches_no_lookup(self):
        with patch("search.get_customers_by_name") as by_name:
            self.assertEqual(search.search_customers("  "), {"type": "empty", "customers": []})
        by_name.assert_not_called()


@unittest.skipUnless(LIVE, "set RUN_LIVE_TESTS=1 to hit Supabase")
class LiveSearchTests(unittest.TestCase):
    def ids(self, text):
        return [c["customer_id"] for c in search.search_customers(text)["customers"]]

    def test_every_input_type_finds_grace_kim(self):
        for text in ("ORD-1003", "CUST-003", "GRACE.KIM@example.com", "+64 21 555 0103"):
            self.assertEqual(self.ids(text), ["CUST-003"], text)

    def test_shared_name_returns_both_customers_in_any_case(self):
        for text in ("Grace Kim", "grace kim", "  GRACE KIM "):
            self.assertEqual(self.ids(text), ["CUST-003", "CUST-006"], text)

    def test_the_second_grace_kim_is_found_by_her_own_identifiers(self):
        for text in ("ORD-1006", "grace.kim.dunedin@example.com", "021 555 0106"):
            self.assertEqual(self.ids(text), ["CUST-006"], text)

    def test_nothing_found(self):
        for text in ("ORD-9999", "CUST-999", "nobody@example.com", "021 555 9999", "Nobody Here"):
            self.assertEqual(self.ids(text), [], text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
