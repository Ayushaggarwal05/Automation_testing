"""
Unit tests for PolicyEngine module.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from policies import PolicyEngine, PolicyRule


class TestPolicyEngine(unittest.TestCase):
    def setUp(self):
        self.engine = PolicyEngine(default_effect="DENY")

    def test_create_and_get_policy(self):
        policy = self.engine.create_policy(
            name="allow_admin_all",
            effect="ALLOW",
            actions=["*"],
            resources=["*"],
            roles=["admin"],
            description="Full admin access",
        )
        self.assertIsInstance(policy, PolicyRule)
        self.assertEqual(policy.name, "allow_admin_all")
        self.assertEqual(policy.effect, "ALLOW")

        retrieved = self.engine.get_policy(policy.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "allow_admin_all")

    def test_create_policy_validation(self):
        with self.assertRaises(ValueError):
            self.engine.create_policy("", effect="ALLOW")
        with self.assertRaises(ValueError):
            self.engine.create_policy("test", effect="INVALID_EFFECT")

    def test_rbac_evaluation(self):
        # Admin allows all
        self.engine.create_policy(name="admin_rule", effect="ALLOW", actions=["*"], resources=["*"], roles=["admin"])
        # User allows read only on items
        self.engine.create_policy(name="user_read_items", effect="ALLOW", actions=["read"], resources=["items"], roles=["user"])

        # Admin can delete items
        eval_admin = self.engine.evaluate(subject_role="admin", action="delete", resource="items")
        self.assertTrue(eval_admin["allowed"])
        self.assertEqual(eval_admin["decision"], "ALLOW")

        # User can read items
        eval_user_read = self.engine.evaluate(subject_role="user", action="read", resource="items")
        self.assertTrue(eval_user_read["allowed"])

        # User cannot delete items (default deny)
        eval_user_del = self.engine.evaluate(subject_role="user", action="delete", resource="items")
        self.assertFalse(eval_user_del["allowed"])
        self.assertEqual(eval_user_del["decision"], "DENY")

    def test_abac_conditions_evaluation(self):
        # Allow deployment only in staging environment
        self.engine.create_policy(
            name="staging_deploy_only",
            effect="ALLOW",
            actions=["deploy"],
            resources=["service"],
            roles=["developer"],
            conditions={"env": "staging"},
        )

        # In staging -> ALLOW
        eval_staging = self.engine.evaluate(
            subject_role="developer", action="deploy", resource="service", context={"env": "staging"}
        )
        self.assertTrue(eval_staging["allowed"])

        # In prod -> DENY
        eval_prod = self.engine.evaluate(
            subject_role="developer", action="deploy", resource="service", context={"env": "prod"}
        )
        self.assertFalse(eval_prod["allowed"])

    def test_deny_overrides_allow(self):
        # Allow rule for all developers
        self.engine.create_policy(name="allow_dev", effect="ALLOW", actions=["write"], resources=["repo"], roles=["developer"])
        # Explicit deny for contractor devs
        self.engine.create_policy(
            name="deny_contractor",
            effect="DENY",
            actions=["write"],
            resources=["repo"],
            roles=["developer"],
            conditions={"is_contractor": True},
        )

        # Regular dev
        eval_reg = self.engine.evaluate(subject_role="developer", action="write", resource="repo", context={"is_contractor": False})
        self.assertTrue(eval_reg["allowed"])

        # Contractor dev -> DENY overrides ALLOW
        eval_contractor = self.engine.evaluate(subject_role="developer", action="write", resource="repo", context={"is_contractor": True})
        self.assertFalse(eval_contractor["allowed"])
        self.assertEqual(eval_contractor["decision"], "DENY")

    def test_list_delete_and_stats(self):
        p1 = self.engine.create_policy(name="p1", effect="ALLOW")
        p2 = self.engine.create_policy(name="p2", effect="DENY")

        policies_list = self.engine.list_policies()
        self.assertEqual(len(policies_list), 2)

        stats = self.engine.get_stats()
        self.assertEqual(stats["total_policies"], 2)
        self.assertEqual(stats["allow_policies"], 1)
        self.assertEqual(stats["deny_policies"], 1)

        self.assertTrue(self.engine.delete_policy(p1.id))
        self.assertFalse(self.engine.delete_policy("non_existent"))
        self.assertEqual(len(self.engine.list_policies()), 1)

        self.engine.clear()
        self.assertEqual(len(self.engine.list_policies()), 0)


if __name__ == "__main__":
    unittest.main()
