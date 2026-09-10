"""
Unit tests for utils module.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from utils import validate_item_payload, format_response, sanitize_input


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


if __name__ == "__main__":
    unittest.main()
