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

    def test_has_and_keys(self):
        self.cache.set("alpha", 100)
        self.cache.set("beta", 200)
        self.assertTrue(self.cache.has("alpha"))
        self.assertFalse(self.cache.has("gamma"))
        self.assertCountEqual(self.cache.keys(), ["alpha", "beta"])

    def test_get_or_set(self):
        call_count = [0]

        def factory():
            call_count[0] += 1
            return "computed_val"

        # First access invokes factory
        val1 = self.cache.get_or_set("computed", factory)
        self.assertEqual(val1, "computed_val")
        self.assertEqual(call_count[0], 1)

        # Second access returns cached value without calling factory
        val2 = self.cache.get_or_set("computed", factory)
        self.assertEqual(val2, "computed_val")
        self.assertEqual(call_count[0], 1)

    def test_cleanup_expired(self):
        self.cache.set("quick", "vanish", ttl=1)
        self.cache.set("persistent", "stay", ttl=60)
        time.sleep(1.1)
        evicted = self.cache.cleanup_expired()
        self.assertEqual(evicted, 1)
        self.assertEqual(self.cache.size(), 1)
        self.assertEqual(self.cache.keys(), ["persistent"])


if __name__ == "__main__":
    unittest.main()

