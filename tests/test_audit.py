"""
Unit tests for AuditLogManager module.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from audit import AuditLogManager, AuditRecord


class TestAuditLogManager(unittest.TestCase):
    def setUp(self):
        self.manager = AuditLogManager()

    def test_record_and_query_event(self):
        record = self.manager.record_event(
            actor="admin_user",
            action="item_deleted",
            category="DATA_MUTATION",
            severity="WARNING",
            details={"item_id": 42},
        )
        self.assertIsInstance(record, AuditRecord)
        self.assertEqual(record.actor, "admin_user")
        self.assertEqual(record.action, "item_deleted")
        self.assertEqual(len(record.record_hash), 64)

        logs = self.manager.query_logs(actor="admin")
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["id"], record.id)

    def test_record_validation(self):
        with self.assertRaises(ValueError):
            self.manager.record_event("", "action")
        with self.assertRaises(ValueError):
            self.manager.record_event("actor", "")
        with self.assertRaises(ValueError):
            self.manager.record_event("actor", "action", category="INVALID_CAT")
        with self.assertRaises(ValueError):
            self.manager.record_event("actor", "action", severity="INVALID_SEV")

    def test_cryptographic_integrity_verification(self):
        self.manager.record_event("user1", "login", category="AUTH", severity="INFO")
        self.manager.record_event("user2", "update", category="DATA_MUTATION", severity="INFO")
        self.manager.record_event("user3", "delete", category="DATA_MUTATION", severity="CRITICAL")

        integrity = self.manager.verify_integrity()
        self.assertTrue(integrity["valid"])
        self.assertEqual(integrity["total_verified"], 3)

    def test_tamper_detection(self):
        self.manager.record_event("user1", "action1")
        self.manager.record_event("user2", "action2")

        # Tamper with internal record
        self.manager._records[0].action = "tampered_action"

        integrity = self.manager.verify_integrity()
        self.assertFalse(integrity["valid"])
        self.assertIn("Tampered", integrity["error"])

    def test_export_json_and_csv(self):
        self.manager.record_event("alice", "create", category="DATA_MUTATION")
        self.manager.record_event("bob", "read", category="SYSTEM")

        json_export = self.manager.export_logs(format_type="json")
        self.assertEqual(json_export["format"], "json")
        self.assertEqual(len(json_export["data"]), 2)

        csv_export = self.manager.export_logs(format_type="csv")
        self.assertEqual(csv_export["format"], "csv")
        self.assertIn("id,timestamp,actor,action", csv_export["data"])

    def test_stats_and_clear(self):
        self.manager.record_event("alice", "login", category="AUTH", severity="INFO")
        self.manager.record_event("bob", "elevate_role", category="ADMIN", severity="CRITICAL")

        stats = self.manager.get_stats()
        self.assertEqual(stats["total_records"], 2)
        self.assertEqual(stats["by_category"]["AUTH"], 1)
        self.assertEqual(stats["by_category"]["ADMIN"], 1)
        self.assertEqual(stats["by_severity"]["CRITICAL"], 1)

        self.manager.clear()
        self.assertEqual(self.manager.get_stats()["total_records"], 0)
        self.assertEqual(self.manager._last_hash, "0" * 64)


if __name__ == "__main__":
    unittest.main()
