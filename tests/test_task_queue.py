"""
Unit tests for TaskQueue and background job processor.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from task_queue import TaskQueue, TaskStatus


class TestTaskQueue(unittest.TestCase):
    def setUp(self):
        self.queue = TaskQueue()

    def test_enqueue_and_get(self):
        task = self.queue.enqueue("send_notification", {"user": "alice"})
        self.assertEqual(task.status, TaskStatus.PENDING)
        
        fetched = self.queue.get_task(task.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.task_name, "send_notification")

    def test_process_successful_task(self):
        def sample_worker(payload):
            return f"Processed for {payload['user']}"

        task = self.queue.enqueue("generate_report", {"user": "bob"}, handler=sample_worker)
        processed = self.queue.process_next()
        
        self.assertIsNotNone(processed)
        self.assertEqual(processed.status, TaskStatus.COMPLETED)
        self.assertEqual(processed.result, "Processed for bob")

    def test_process_failing_task_retry(self):
        def failing_worker(payload):
            raise ValueError("Service down")

        task = self.queue.enqueue("sync_data", {}, handler=failing_worker)
        task.max_retries = 1

        # First run fails and hits max retries -> FAILED
        processed = self.queue.process_next()
        self.assertEqual(processed.status, TaskStatus.FAILED)
        self.assertIn("Service down", processed.error)

    def test_cancel_task(self):
        task = self.queue.enqueue("cleanup_job", {})
        self.assertTrue(self.queue.cancel_task(task.id))
        self.assertEqual(task.status, TaskStatus.CANCELLED)
        # Cannot cancel non-pending or non-existent task
        self.assertFalse(self.queue.cancel_task("non-existent-id"))
        self.assertFalse(self.queue.cancel_task(task.id))

    def test_process_all(self):
        self.queue.enqueue("task_1", {})
        self.queue.enqueue("task_2", {})
        self.queue.enqueue("task_3", {})
        
        processed = self.queue.process_all()
        self.assertEqual(len(processed), 3)
        self.assertTrue(all(t.status == TaskStatus.COMPLETED for t in processed))
        self.assertIsNone(self.queue.process_next())

    def test_metrics_and_clear(self):
        self.queue.enqueue("task_a", {})
        self.queue.enqueue("task_b", {})
        self.queue.process_next()

        metrics = self.queue.get_metrics()
        self.assertEqual(metrics["total"], 2)
        self.assertEqual(metrics[TaskStatus.COMPLETED.value], 1)
        self.assertEqual(metrics[TaskStatus.PENDING.value], 1)

        self.queue.clear()
        cleared_metrics = self.queue.get_metrics()
        self.assertEqual(cleared_metrics["total"], 0)


if __name__ == "__main__":
    unittest.main()

