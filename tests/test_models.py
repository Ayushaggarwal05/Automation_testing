"""
Unit tests for data models.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from models import ItemModel, UserModel


class TestModels(unittest.TestCase):
    def test_item_model_creation(self):
        item = ItemModel(id=1, name="Test Widget", status="active")
        self.assertEqual(item.id, 1)
        self.assertEqual(item.name, "Test Widget")
        self.assertEqual(item.status, "active")
        
        d = item.to_dict()
        self.assertEqual(d["id"], 1)
        self.assertEqual(d["name"], "Test Widget")

    def test_item_status_update(self):
        item = ItemModel(id=2, name="Updatable Widget")
        item.update_status("archived")
        self.assertEqual(item.status, "archived")

        with self.assertRaises(ValueError):
            item.update_status("invalid_status")

    def test_user_model(self):
        admin = UserModel(username="admin_user", role="admin")
        self.assertTrue(admin.is_admin())
        self.assertFalse(admin.is_expired())

        user = UserModel(username="regular_user", role="user")
        self.assertFalse(user.is_admin())


if __name__ == "__main__":
    unittest.main()
