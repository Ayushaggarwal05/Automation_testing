"""
Unit tests for VaultManager module.
"""

import unittest
import time
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from vault import VaultManager, SecretEntry


class TestVaultManager(unittest.TestCase):
    def setUp(self):
        self.manager = VaultManager(master_key="test-secret-key")

    def test_store_and_get_secret(self):
        entry = self.manager.store_secret(
            name="stripe_api_key",
            value="sk_test_123456789",
            description="Payment gateway secret",
            tags=["finance", "api"],
            actor="test_admin",
        )
        self.assertIsInstance(entry, SecretEntry)
        self.assertEqual(entry.name, "stripe_api_key")
        self.assertEqual(entry.current_version, 1)

        # Masked get
        masked_res = self.manager.get_secret("stripe_api_key", reveal=False)
        self.assertTrue(masked_res["found"])
        self.assertEqual(masked_res["value"], "********")

        # Revealed get
        revealed_res = self.manager.get_secret("stripe_api_key", reveal=True)
        self.assertTrue(revealed_res["found"])
        self.assertEqual(revealed_res["value"], "sk_test_123456789")

    def test_duplicate_secret_fails(self):
        self.manager.store_secret(name="db_password", value="pass1")
        with self.assertRaises(ValueError):
            self.manager.store_secret(name="db_password", value="pass2")

    def test_rotate_secret(self):
        self.manager.store_secret(name="jwt_secret", value="secret_v1")
        entry = self.manager.rotate_secret("jwt_secret", new_value="secret_v2", actor="admin")

        self.assertEqual(entry.current_version, 2)
        self.assertEqual(len(entry.versions), 2)

        # Latest version get
        res_v2 = self.manager.get_secret("jwt_secret", reveal=True)
        self.assertEqual(res_v2["value"], "secret_v2")
        self.assertEqual(res_v2["version"], 2)

        # Specific version get
        res_v1 = self.manager.get_secret("jwt_secret", reveal=True, version=1)
        self.assertEqual(res_v1["value"], "secret_v1")
        self.assertEqual(res_v1["version"], 1)

    def test_revoke_secret(self):
        self.manager.store_secret(name="temp_token", value="xyz")
        self.assertTrue(self.manager.revoke_secret("temp_token"))
        self.assertFalse(self.manager.revoke_secret("temp_token"))  # Already revoked

        get_res = self.manager.get_secret("temp_token")
        self.assertFalse(get_res["found"])

    def test_expired_secret(self):
        # 0.05 second TTL
        self.manager.store_secret(name="expiring_token", value="exp123", ttl_seconds=0.05)
        time.sleep(0.06)

        get_res = self.manager.get_secret("expiring_token")
        self.assertFalse(get_res["found"])
        self.assertIn("expired", get_res["error"])

    def test_list_and_stats(self):
        self.manager.store_secret(name="s1", value="v1", tags=["infra"])
        self.manager.store_secret(name="s2", value="v2", tags=["app"])
        self.manager.store_secret(name="s3", value="v3", tags=["infra"])
        self.manager.revoke_secret("s3")

        # List active only
        active = self.manager.list_secrets()
        self.assertEqual(len(active), 2)

        # List by tag
        infra_secrets = self.manager.list_secrets(tag_filter="infra", include_revoked=True)
        self.assertEqual(len(infra_secrets), 2)

        stats = self.manager.get_stats()
        self.assertEqual(stats["total_secrets"], 3)
        self.assertEqual(stats["active_secrets"], 2)
        self.assertEqual(stats["revoked_secrets"], 1)

        self.manager.clear()
        self.assertEqual(len(self.manager.list_secrets()), 0)


if __name__ == "__main__":
    unittest.main()
