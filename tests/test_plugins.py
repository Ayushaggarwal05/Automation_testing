"""
Unit tests for PluginManager and plugin lifecycle.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from plugins import PluginManager, BasePlugin, AuditLogPlugin


class CustomBlockingPlugin(BasePlugin):
    def on_load(self) -> None:
        pass

    def before_request(self, context):
        if context.get("block_me"):
            return {"error": "Blocked by CustomBlockingPlugin", "status_code": 403}
        return None


class TestPluginManager(unittest.TestCase):
    def setUp(self):
        self.manager = PluginManager()

    def test_register_and_list(self):
        audit_plugin = AuditLogPlugin()
        self.manager.register(audit_plugin)
        
        plugin_list = self.manager.list_plugins()
        self.assertEqual(len(plugin_list), 1)
        self.assertEqual(plugin_list[0]["name"], "AuditLogPlugin")
        self.assertTrue(plugin_list[0]["enabled"])

    def test_before_request_hook_blocking(self):
        self.manager.register(CustomBlockingPlugin(name="Blocker"))
        
        # Allowed request
        res_allowed = self.manager.trigger_before_request({"endpoint": "/items"})
        self.assertIsNone(res_allowed)

        # Blocked request
        res_blocked = self.manager.trigger_before_request({"endpoint": "/items", "block_me": True})
        self.assertIsNotNone(res_blocked)
        self.assertEqual(res_blocked["status_code"], 403)

    def test_after_response_hook(self):
        audit_plugin = AuditLogPlugin()
        self.manager.register(audit_plugin)

        ctx = {"endpoint": "/health"}
        resp = {"status": "ok", "status_code": 200}
        out_resp = self.manager.trigger_after_response(ctx, resp)

        self.assertEqual(out_resp["status_code"], 200)
        self.assertEqual(len(audit_plugin.log), 1)
        self.assertEqual(audit_plugin.log[0]["endpoint"], "/health")

    def test_unregister(self):
        plugin = AuditLogPlugin()
        self.manager.register(plugin)
        self.assertTrue(self.manager.unregister("AuditLogPlugin"))
        self.assertFalse(self.manager.unregister("AuditLogPlugin"))
        self.assertEqual(len(self.manager.list_plugins()), 0)


if __name__ == "__main__":
    unittest.main()
