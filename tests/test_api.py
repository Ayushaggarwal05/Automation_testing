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
        self.assertEqual(res["version"], "2.4.0")

    def test_list_plugins(self):
        res = self.api.list_plugins(self.token)
        self.assertEqual(res["status_code"], 200)
        self.assertIn("plugins", res)

    def test_webhook_endpoints(self):
        res = self.api.register_webhook(self.token, "item_created", "https://example.com/item-hook")
        self.assertEqual(res["status_code"], 201)
        self.assertEqual(res["subscription"]["event_name"], "item_created")

        list_res = self.api.list_webhooks(self.token, event_filter="item_created")
        self.assertEqual(list_res["status_code"], 200)
        self.assertGreaterEqual(list_res["count"], 1)

    def test_job_queue_endpoints(self):
        # Enqueue job
        res = self.api.enqueue_job(self.token, "export_csv", {"target": "user_items"})
        self.assertEqual(res["status_code"], 202)
        task_id = res["task"]["id"]

        # Check job status
        status_res = self.api.get_job_status(self.token, task_id)
        self.assertEqual(status_res["status_code"], 200)
        self.assertEqual(status_res["task"]["status"], "PENDING")

    def test_get_metrics(self):
        self.api.health_check()
        metrics_res = self.api.get_metrics(self.token)
        self.assertEqual(metrics_res["status_code"], 200)
        self.assertIn("uptime_seconds", metrics_res["metrics"])
        self.assertGreaterEqual(metrics_res["metrics"]["total_requests"], 1)

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

    def test_get_items_pagination_and_sorting(self):
        # Test pagination limit
        res_paginated = self.api.get_items(self.token, limit=1, offset=0)
        self.assertEqual(res_paginated["status_code"], 200)
        self.assertEqual(len(res_paginated["data"]), 1)
        self.assertEqual(res_paginated["count"], 1)

        # Test reverse sorting by name
        res_sorted = self.api.get_items(self.token, sort_by="name", reverse=True)
        self.assertEqual(res_sorted["status_code"], 200)
        names = [item["name"] for item in res_sorted["data"]]
        self.assertEqual(names, sorted(names, reverse=True))

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

    def test_search_items(self):
        # Search matching items
        search_res = self.api.search_items(self.token, "Alpha")
        self.assertEqual(search_res["status_code"], 200)
        self.assertEqual(search_res["count"], 1)
        self.assertEqual(search_res["data"][0]["name"], "Item Alpha")

        # Search non-matching items
        empty_res = self.api.search_items(self.token, "NonExistent")
        self.assertEqual(empty_res["status_code"], 200)
        self.assertEqual(empty_res["count"], 0)

    def test_batch_operations(self):
        # Batch add items
        names = ["Batch One", "Batch Two", "Batch Three"]
        batch_res = self.api.batch_add_items(self.token, names)
        self.assertEqual(batch_res["status_code"], 201)
        self.assertEqual(len(batch_res["items"]), 3)

        # Batch delete items
        ids = [item["id"] for item in batch_res["items"]]
        del_batch_res = self.api.batch_delete_items(self.token, ids)
        self.assertEqual(del_batch_res["status_code"], 200)
        self.assertEqual(del_batch_res["deleted_count"], 3)

    def test_audit_events(self):
        # Clear logs and perform operations
        self.api.events.clear_logs()
        self.api.add_item(self.token, "Event Test Item")
        self.api.update_item_status(self.token, 1, "completed")

        res = self.api.get_audit_events(self.token)
        self.assertEqual(res["status_code"], 200)
        self.assertGreaterEqual(res["count"], 2)

    def test_get_item_summary(self):
        res = self.api.get_item_summary(self.token)
        self.assertEqual(res["status_code"], 200)
        self.assertEqual(res["total_items"], 2)
        self.assertIn("active", res["status_breakdown"])
        self.assertIn("pending", res["status_breakdown"])

    def test_batch_update_status(self):
        res = self.api.batch_update_status(self.token, [1, 2], "archived")
        self.assertEqual(res["status_code"], 200)
        self.assertEqual(res["updated_count"], 2)
        
        items_res = self.api.get_items(self.token)
        self.assertTrue(all(item["status"] == "archived" for item in items_res["data"]))

    def test_export_items_json_and_csv(self):
        json_res = self.api.export_items(self.token, format_type="json")
        self.assertEqual(json_res["status_code"], 200)
        self.assertEqual(json_res["format"], "json")
        self.assertEqual(len(json_res["data"]), 2)

        csv_res = self.api.export_items(self.token, format_type="csv")
        self.assertEqual(csv_res["status_code"], 200)
        self.assertIn("id,name,status", csv_res["data"])

    def test_clear_items(self):
        res = self.api.clear_items(self.token)
        self.assertEqual(res["status_code"], 200)
        self.assertEqual(res["cleared_count"], 2)

        items_res = self.api.get_items(self.token)
        self.assertEqual(items_res["count"], 0)

    def test_notification_endpoints(self):
        # Send notification
        send_res = self.api.send_notification(
            self.token,
            recipient="ops@example.com",
            message="Deployment successful",
            channel="slack",
            priority="high",
            subject="Deploy Alert",
        )
        self.assertEqual(send_res["status_code"], 201)
        notif_id = send_res["notification"]["id"]

        # List notifications
        list_res = self.api.list_notifications(self.token, channel="slack")
        self.assertEqual(list_res["status_code"], 200)
        self.assertGreaterEqual(list_res["count"], 1)

        # Get notification
        get_res = self.api.get_notification(self.token, notif_id)
        self.assertEqual(get_res["status_code"], 200)
        self.assertEqual(get_res["notification"]["recipient"], "ops@example.com")

        # Cancel notification
        cancel_res = self.api.cancel_notification(self.token, notif_id)
        self.assertEqual(cancel_res["status_code"], 200)

        # Get notification stats
        stats_res = self.api.get_notification_stats(self.token)
        self.assertEqual(stats_res["status_code"], 200)
        self.assertIn("total_notifications", stats_res["stats"])

    def test_workflow_endpoints(self):
        steps = [
            {"name": "Init Step", "action_type": "log", "params": {"message": "Pipeline init"}},
            {"name": "Notify Ops", "action_type": "notification", "params": {"recipient": "alerts@example.com"}},
        ]
        # Create workflow
        create_res = self.api.create_workflow(
            self.token, name="CI Pipeline", steps=steps, description="Build & test flow"
        )
        self.assertEqual(create_res["status_code"], 201)
        wf_id = create_res["workflow"]["id"]

        # List workflows
        list_res = self.api.list_workflows(self.token)
        self.assertEqual(list_res["status_code"], 200)
        self.assertGreaterEqual(list_res["count"], 1)

        # Get workflow
        get_res = self.api.get_workflow(self.token, wf_id)
        self.assertEqual(get_res["status_code"], 200)
        self.assertEqual(get_res["workflow"]["name"], "CI Pipeline")

        # Execute workflow
        exec_res = self.api.execute_workflow(self.token, wf_id, context={"run_id": "run-123"})
        self.assertEqual(exec_res["status_code"], 200)
        exec_id = exec_res["execution"]["id"]
        self.assertEqual(exec_res["execution"]["status"], "COMPLETED")

        # List executions
        execs_list = self.api.list_workflow_executions(self.token, workflow_id=wf_id)
        self.assertEqual(execs_list["status_code"], 200)
        self.assertGreaterEqual(execs_list["count"], 1)

        # Get execution
        exec_detail = self.api.get_workflow_execution(self.token, exec_id)
        self.assertEqual(exec_detail["status_code"], 200)
        self.assertEqual(exec_detail["execution"]["id"], exec_id)


if __name__ == "__main__":
    unittest.main()



