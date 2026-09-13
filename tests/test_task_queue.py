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


if __name__ == "__main__":
    unittest.main()
