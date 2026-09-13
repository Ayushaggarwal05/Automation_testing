"""
Unit tests for CacheManager.
"""

import unittest
import time
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from cache import CacheManager


class TestCacheManager(unittest.TestCase):
    def setUp(self):
        self.cache = CacheManager(default_ttl=60)

    def test_set_and_get(self):
        self.cache.set("key1", "value1")
        self.assertEqual(self.cache.get("key1"), "value1")
        self.assertIsNone(self.cache.get("non_existent"))

    def test_delete_and_clear(self):
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        self.assertTrue(self.cache.delete("key1"))
        self.assertFalse(self.cache.delete("key1"))
        self.assertEqual(self.cache.size(), 1)

        self.cache.clear()
        self.assertEqual(self.cache.size(), 0)

    def test_expiration(self):
        # 1-second TTL
        self.cache.set("short_lived", "data", ttl=1)
        self.assertEqual(self.cache.get("short_lived"), "data")
        time.sleep(1.1)
        self.assertIsNone(self.cache.get("short_lived"))


if __name__ == "__main__":
    unittest.main()
