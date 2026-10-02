"""
Unit tests for LeaseManager module.
"""

import unittest
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.leases import LeaseManager, LeaseLock, LockAcquireResult


class TestLeaseManager(unittest.TestCase):
    def setUp(self):
        self.manager = LeaseManager(default_duration=2.0, max_duration=10.0, fencing_token_start=100)

    def test_acquire_and_inspect_lock(self):
        res = self.manager.acquire(
            resource_key="db_migration",
            holder="worker_node_1",
            duration_seconds=5.0,
            metadata={"version": "v1.2"},
        )
        self.assertTrue(res.acquired)
        self.assertEqual(res.fencing_token, 101)
        self.assertEqual(res.holder, "worker_node_1")

        lock = self.manager.inspect("db_migration")
        self.assertIsNotNone(lock)
        self.assertEqual(lock["holder"], "worker_node_1")
        self.assertEqual(lock["fencing_token"], 101)

    def test_lock_conflict(self):
        # 1st holder acquires
        res1 = self.manager.acquire("exclusive_task", "node_a", duration_seconds=5.0)
        self.assertTrue(res1.acquired)

        # 2nd holder tries to acquire the same resource -> conflict
        res2 = self.manager.acquire("exclusive_task", "node_b", duration_seconds=5.0)
        self.assertFalse(res2.acquired)
        self.assertEqual(res2.current_holder, "node_a")
        self.assertGreater(res2.retry_after, 0)

    def test_renew_and_release_lock(self):
        res = self.manager.acquire("long_job", "node_c", duration_seconds=2.0)
        self.assertTrue(res.acquired)
        token = res.fencing_token

        # Renew
        renew_res = self.manager.renew("long_job", "node_c", token, extension_seconds=5.0)
        self.assertTrue(renew_res.acquired)
        self.assertEqual(renew_res.lock["renewal_count"], 1)

        # Release
        released = self.manager.release("long_job", "node_c", token)
        self.assertTrue(released)

        # Re-acquire by another node is now immediately possible
        res_after = self.manager.acquire("long_job", "node_d", duration_seconds=2.0)
        self.assertTrue(res_after.acquired)

    def test_force_break_lock(self):
        self.manager.acquire("stuck_job", "crashed_worker", duration_seconds=10.0)
        broken = self.manager.force_break("stuck_job", reason="Worker dead")
        self.assertTrue(broken)

        res = self.manager.acquire("stuck_job", "healthy_worker", duration_seconds=5.0)
        self.assertTrue(res.acquired)

    def test_lease_expiry(self):
        # Acquire short lease (0.1 seconds)
        self.manager.acquire("short_key", "fast_node", duration_seconds=0.1)
        time.sleep(0.15)

        # Another node should be able to acquire since expired
        res = self.manager.acquire("short_key", "new_node", duration_seconds=2.0)
        self.assertTrue(res.acquired)

    def test_lease_stats(self):
        res = self.manager.acquire("res_1", "worker_1")
        self.manager.renew("res_1", "worker_1", res.fencing_token)
        self.manager.release("res_1", "worker_1", res.fencing_token)

        stats = self.manager.get_stats()
        self.assertEqual(stats["acquisitions_count"], 1)
        self.assertEqual(stats["renewals_count"], 1)
        self.assertEqual(stats["releases_count"], 1)


if __name__ == "__main__":
    unittest.main()
