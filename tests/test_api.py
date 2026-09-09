"""
Unit tests for AuthService and APIService.
"""

import unittest
import sys
import os

# Add src to python path for testing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from auth import AuthService
from api import APIService


class TestAuthService(unittest.TestCase):
    def setUp(self):
        self.auth = AuthService()

    def test_token_generation_and_validation(self):
        token = self.auth.generate_token("test_user")
        self.assertTrue(self.auth.validate_token(token))
        self.assertEqual(self.auth.get_user_from_token(token), "test_user")

    def test_role_assignment(self):
        admin_token = self.auth.generate_token("admin_user", role="admin")
        self.assertEqual(self.auth.get_role_from_token(admin_token), "admin")
        self.assertTrue(self.auth.has_role(admin_token, "admin"))
        self.assertFalse(self.auth.has_role(admin_token, "guest"))


class TestAPIService(unittest.TestCase):
    def setUp(self):
        self.api = APIService()
        self.token = self.api.auth_service.generate_token("tester")

    def test_health_check(self):
        res = self.api.health_check()
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["version"], "1.1.0")

    def test_get_items_unauthorized(self):
        res = self.api.get_items()
        self.assertEqual(res["status_code"], 401)

    def test_get_items_authorized(self):
        res = self.api.get_items(self.token)
        self.assertEqual(res["status_code"], 200)
        self.assertTrue(len(res["data"]) >= 2)
        self.assertEqual(res["count"], len(res["data"]))

    def test_get_items_filtered_by_status(self):
        res = self.api.get_items(self.token, status="active")
        self.assertEqual(res["status_code"], 200)
        self.assertTrue(all(item["status"] == "active" for item in res["data"]))

    def test_add_and_delete_item(self):
        # Add item
        add_res = self.api.add_item(self.token, "New Item")
        self.assertEqual(add_res["status_code"], 201)
        item_id = add_res["item"]["id"]

        # Get item by ID
        get_res = self.api.get_item_by_id(self.token, item_id)
        self.assertEqual(get_res["status_code"], 200)
        self.assertEqual(get_res["data"]["name"], "New Item")

        # Delete item
        del_res = self.api.delete_item(self.token, item_id)
        self.assertEqual(del_res["status_code"], 200)


if __name__ == "__main__":
    unittest.main()
