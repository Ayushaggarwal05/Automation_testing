"""
Unit tests for WorkflowEngine module.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from workflows import WorkflowEngine, Workflow, WorkflowExecution


class TestWorkflowEngine(unittest.TestCase):
    def setUp(self):
        self.engine = WorkflowEngine()

    def test_create_workflow(self):
        steps = [
            {"name": "Step 1", "action_type": "log", "params": {"message": "Starting job"}},
            {"name": "Step 2", "action_type": "notification", "params": {"recipient": "dev@example.com"}},
        ]
        wf = self.engine.create_workflow("Order Processing", steps, description="Process customer orders")
        self.assertIsInstance(wf, Workflow)
        self.assertEqual(wf.name, "Order Processing")
        self.assertEqual(len(wf.steps), 2)
        self.assertTrue(wf.enabled)

    def test_create_workflow_validation(self):
        with self.assertRaises(ValueError):
            self.engine.create_workflow("", [{"action_type": "log"}])
        with self.assertRaises(ValueError):
            self.engine.create_workflow("Test", [])
        with self.assertRaises(ValueError):
            self.engine.create_workflow("Test", [{"action_type": "invalid_action"}])

    def test_execute_workflow_success(self):
        steps = [
            {"name": "Log Step", "action_type": "log", "params": {"message": "Hello World"}},
            {"name": "Custom Step", "action_type": "custom", "params": {"value": 42}},
        ]
        wf = self.engine.create_workflow("Success Flow", steps)
        execution = self.engine.execute_workflow(wf.id, context={"env": "test"})

        self.assertIsInstance(execution, WorkflowExecution)
        self.assertEqual(execution.status, "COMPLETED")
        self.assertEqual(len(execution.step_results), 2)
        self.assertEqual(execution.step_results[0]["status"], "COMPLETED")
        self.assertIsNotNone(execution.completed_at)

    def test_execute_workflow_failure_with_stop_on_failure(self):
        def failing_handler(params, ctx):
            raise RuntimeError("Database connection timed out")

        self.engine.register_handler("failing_action", failing_handler)

        steps = [
            {"name": "Log Step", "action_type": "log", "params": {"message": "Begin"}},
            {"name": "Failing Step", "action_type": "custom", "params": {}},  # Will swap to handler
        ]
        wf = self.engine.create_workflow("Fail Flow", steps)
        
        # Override step action to failing handler
        wf.steps[1]["action_type"] = "failing_action"

        execution = self.engine.execute_workflow(wf.id)
        self.assertEqual(execution.status, "FAILED")
        self.assertIn("failed", execution.error_message)

    def test_list_and_delete_workflow(self):
        wf1 = self.engine.create_workflow("WF 1", [{"action_type": "log"}])
        wf2 = self.engine.create_workflow("WF 2", [{"action_type": "event", "params": {"event_name": "item_done"}}])

        wfs = self.engine.list_workflows()
        self.assertEqual(len(wfs), 2)

        self.assertTrue(self.engine.delete_workflow(wf1.id))
        self.assertFalse(self.engine.delete_workflow("invalid_id"))
        self.assertEqual(len(self.engine.list_workflows()), 1)

    def test_list_and_get_executions(self):
        wf = self.engine.create_workflow("Exec Test", [{"action_type": "log"}])
        exec1 = self.engine.execute_workflow(wf.id)
        exec2 = self.engine.execute_workflow(wf.id)

        all_execs = self.engine.list_executions()
        self.assertEqual(len(all_execs), 2)

        retrieved = self.engine.get_execution(exec1.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, exec1.id)

    def test_clear(self):
        wf = self.engine.create_workflow("Clear Test", [{"action_type": "log"}])
        self.engine.execute_workflow(wf.id)
        self.assertEqual(len(self.engine.list_workflows()), 1)
        self.assertEqual(len(self.engine.list_executions()), 1)

        self.engine.clear()
        self.assertEqual(len(self.engine.list_workflows()), 0)
        self.assertEqual(len(self.engine.list_executions()), 0)


if __name__ == "__main__":
    unittest.main()
