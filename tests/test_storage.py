"""
Unit tests for storage abstraction layer.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from storage import InMemoryStorage


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.storage = InMemoryStorage(
            initial_data=[
                {"id": 1, "name": "Item A", "status": "active"},
                {"id": 2, "name": "Item B", "status": "pending"},
            ]
        )

    def test_get_all(self):
        items = self.storage.get_all()
        self.assertEqual(len(items), 2)

    def test_get_by_id(self):
        item = self.storage.get_by_id(1)
        self.assertIsNotNone(item)
        self.assertEqual(item["name"], "Item A")
        self.assertIsNone(self.storage.get_by_id(999))

    def test_add_and_count(self):
        new_item = self.storage.add({"name": "Item C", "status": "active"})
        self.assertEqual(new_item["id"], 3)
        self.assertEqual(self.storage.count(), 3)

    def test_update(self):
        res = self.storage.update(1, {"status": "archived"})
        self.assertIsNotNone(res)
        self.assertEqual(res["status"], "archived")

    def test_delete(self):
        self.assertTrue(self.storage.delete(1))
        self.assertFalse(self.storage.delete(999))
        self.assertEqual(self.storage.count(), 1)


if __name__ == "__main__":
    unittest.main()
