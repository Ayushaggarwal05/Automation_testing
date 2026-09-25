"""
Unit tests for SchedulerEngine module.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from scheduler import SchedulerEngine, ScheduledJob, JobExecutionRecord


class TestSchedulerEngine(unittest.TestCase):
    def setUp(self):
        self.engine = SchedulerEngine()

    def test_schedule_and_get_job(self):
        job = self.engine.schedule_job(
            name="nightly_backup",
            target_action="data_cleanup",
            interval_seconds=3600,
            cron_expression="0 0 * * *",
            payload={"tables": ["users", "sessions"]},
        )
        self.assertIsInstance(job, ScheduledJob)
        self.assertEqual(job.name, "nightly_backup")
        self.assertEqual(job.interval_seconds, 3600)
        self.assertEqual(job.status, "SCHEDULED")

        retrieved = self.engine.get_job(job.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.target_action, "data_cleanup")

    def test_schedule_validation(self):
        with self.assertRaises(ValueError):
            self.engine.schedule_job("", "data_cleanup")
        with self.assertRaises(ValueError):
            self.engine.schedule_job("test", "")
        with self.assertRaises(ValueError):
            self.engine.schedule_job("test", "data_cleanup", interval_seconds=-5)

    def test_trigger_now_success(self):
        job = self.engine.schedule_job(name="health_probe", target_action="health_check")
        record = self.engine.trigger_now(job.id)

        self.assertIsInstance(record, JobExecutionRecord)
        self.assertEqual(record.status, "COMPLETED")
        self.assertEqual(record.output, {"status": "ok", "ping": "pong"})
        self.assertEqual(job.total_runs, 1)
        self.assertIsNotNone(job.last_run_at)

    def test_trigger_now_failure(self):
        def failing_action(p):
            raise ConnectionRefusedError("Database offline")

        self.engine.register_handler("failing_job", failing_action)
        job = self.engine.schedule_job(name="sync_service", target_action="failing_job")

        record = self.engine.trigger_now(job.id)
        self.assertEqual(record.status, "FAILED")
        self.assertIn("offline", record.error)
        self.assertEqual(job.consecutive_failures, 1)

    def test_pause_and_resume_job(self):
        job = self.engine.schedule_job(name="sync_task", target_action="sync_metrics")

        # Pause
        self.assertTrue(self.engine.pause_job(job.id))
        self.assertEqual(job.status, "PAUSED")
        self.assertFalse(job.enabled)
        self.assertFalse(self.engine.pause_job(job.id))  # Already paused

        # Resume
        self.assertTrue(self.engine.resume_job(job.id))
        self.assertEqual(job.status, "SCHEDULED")
        self.assertTrue(job.enabled)

    def test_cancel_job(self):
        job = self.engine.schedule_job(name="temp_task", target_action="health_check")
        self.assertTrue(self.engine.cancel_job(job.id))
        self.assertEqual(job.status, "CANCELLED")

        with self.assertRaises(ValueError):
            self.engine.trigger_now(job.id)

    def test_list_and_history(self):
        j1 = self.engine.schedule_job("j1", "health_check")
        j2 = self.engine.schedule_job("j2", "data_cleanup")
        self.engine.pause_job(j2.id)

        all_jobs = self.engine.list_jobs()
        self.assertEqual(len(all_jobs), 2)

        enabled_jobs = self.engine.list_jobs(enabled_only=True)
        self.assertEqual(len(enabled_jobs), 1)

        self.engine.trigger_now(j1.id)
        history = self.engine.list_history()
        self.assertEqual(len(history), 1)

    def test_stats_and_clear(self):
        j1 = self.engine.schedule_job("j1", "health_check")
        j2 = self.engine.schedule_job("j2", "data_cleanup")
        self.engine.pause_job(j2.id)
        self.engine.trigger_now(j1.id)

        stats = self.engine.get_stats()
        self.assertEqual(stats["total_jobs"], 2)
        self.assertEqual(stats["active_jobs"], 1)
        self.assertEqual(stats["paused_jobs"], 1)
        self.assertEqual(stats["total_executions"], 1)

        self.engine.clear()
        self.assertEqual(len(self.engine.list_jobs()), 0)


if __name__ == "__main__":
    unittest.main()
