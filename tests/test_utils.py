"""
Unit tests for utils module.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from utils import validate_item_payload, format_response, sanitize_input, validate_email, generate_slug, truncate_string


class TestUtils(unittest.TestCase):
    def test_validate_item_payload_valid(self):
        result = validate_item_payload({"name": " Valid Item "})
        self.assertTrue(result["valid"])
        self.assertEqual(result["sanitized_name"], "Valid Item")

    def test_validate_item_payload_invalid(self):
        # Empty string
        self.assertFalse(validate_item_payload({"name": "   "})["valid"])
        # Non-dict
        self.assertFalse(validate_item_payload("not a dict")["valid"])
        # Missing key
        self.assertFalse(validate_item_payload({})["valid"])
        # Name too long
        self.assertFalse(validate_item_payload({"name": "x" * 101})["valid"])

    def test_format_response(self):
        res = format_response(200, data={"id": 1}, message="Success")
        self.assertEqual(res["status_code"], 200)
        self.assertEqual(res["data"]["id"], 1)
        self.assertEqual(res["message"], "Success")

    def test_sanitize_input(self):
        dirty = "<script>alert('xss')</script>  hello   world  "
        clean = sanitize_input(dirty)
        self.assertEqual(clean, "hello world")

    def test_validate_email(self):
        self.assertTrue(validate_email("user@example.com"))
        self.assertTrue(validate_email("first.last+tag@sub.domain.co.uk"))
        self.assertFalse(validate_email("invalid-email"))
        self.assertFalse(validate_email("@missinguser.com"))
        self.assertFalse(validate_email("user@.com"))
        self.assertFalse(validate_email(""))

    def test_generate_slug(self):
        self.assertEqual(generate_slug("Hello World! 2026"), "hello-world-2026")
        self.assertEqual(generate_slug("  Leading and Trailing  "), "leading-and-trailing")
        self.assertEqual(generate_slug("Special @#$% Characters"), "special-characters")
        self.assertEqual(generate_slug(""), "")

    def test_truncate_string(self):
        self.assertEqual(truncate_string("Short text", 20), "Short text")
        self.assertEqual(truncate_string("This is a long sentence to truncate", 15), "This is a lo...")
        self.assertEqual(truncate_string("Custom suffix test", 10, suffix="--"), "Custom s--")
        self.assertEqual(truncate_string("", 5), "")


if __name__ == "__main__":
    unittest.main()

