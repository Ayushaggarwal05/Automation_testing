"""
Task scheduling and recurring cron execution engine for automated background triggers.
"""

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Callable

try:
    from events import events
except ImportError:
    from src.events import events


JOB_STATUSES = {"SCHEDULED", "RUNNING", "PAUSED", "COMPLETED", "CANCELLED", "FAILED"}


@dataclass
class JobExecutionRecord:
    """Represents a single execution run of a scheduled job."""
    execution_id: str
    job_id: str
    status: str = "COMPLETED"
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScheduledJob:
    """Represents a recurring or one-off scheduled task definition."""
    id: str
    name: str
    target_action: str
    interval_seconds: int = 60
    cron_expression: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    status: str = "SCHEDULED"
    enabled: bool = True
    total_runs: int = 0
    consecutive_failures: int = 0
    created_at: float = field(default_factory=time.time)
    next_run_at: float = field(default_factory=time.time)
    last_run_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SchedulerEngine:
    """Manages scheduling, cron calculation, manual triggers, and execution lifecycle."""

    def __init__(self):
        self._jobs: Dict[str, ScheduledJob] = {}
        self._history: List[JobExecutionRecord] = []
        self._action_handlers: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}
        self._register_default_handlers()

    def _register_default_handlers(self):
        self.register_handler("health_check", lambda p: {"status": "ok", "ping": "pong"})
        self.register_handler("data_cleanup", lambda p: {"status": "ok", "cleaned_records": 0})
        self.register_handler("sync_metrics", lambda p: {"status": "ok", "synced": True})
        self.register_handler("dispatch_event", lambda p: {"status": "ok", "event": p.get("event_name")})

    def register_handler(self, action_name: str, handler: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        """Register a callable handler for a scheduled job action."""
        self._action_handlers[action_name] = handler

    def schedule_job(
        self,
        name: str,
        target_action: str,
        interval_seconds: int = 60,
        cron_expression: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ScheduledJob:
        """Register and schedule a recurring task."""
        if not name or not name.strip():
            raise ValueError("Job name cannot be empty.")
        if not target_action or not target_action.strip():
            raise ValueError("Target action cannot be empty.")
        if interval_seconds <= 0:
            raise ValueError("Interval must be positive.")

        now = time.time()
        job_id = f"job_{uuid.uuid4().hex[:10]}"
        job = ScheduledJob(
            id=job_id,
            name=name.strip(),
            target_action=target_action.strip(),
            interval_seconds=interval_seconds,
            cron_expression=cron_expression,
            payload=payload or {},
            status="SCHEDULED",
            enabled=True,
            created_at=now,
            next_run_at=now + interval_seconds,
            metadata=metadata or {},
        )
        self._jobs[job_id] = job

        events.publish("job_scheduled", {"job_id": job_id, "name": name, "interval": interval_seconds})
        return job

    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        """Retrieve a scheduled job by ID."""
        return self._jobs.get(job_id)

    def list_jobs(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """List all scheduled jobs."""
        jobs = list(self._jobs.values())
        if enabled_only:
            jobs = [j for j in jobs if j.enabled and j.status != "PAUSED"]
        jobs.sort(key=lambda j: j.created_at)
        return [j.to_dict() for j in jobs]

    def pause_job(self, job_id: str) -> bool:
        """Pause a scheduled job."""
        job = self.get_job(job_id)
        if not job or job.status in ("PAUSED", "CANCELLED"):
            return False

        job.status = "PAUSED"
        job.enabled = False
        events.publish("job_paused", {"job_id": job_id, "name": job.name})
        return True

    def resume_job(self, job_id: str) -> bool:
        """Resume a paused scheduled job."""
        job = self.get_job(job_id)
        if not job or job.status != "PAUSED":
            return False

        job.status = "SCHEDULED"
        job.enabled = True
        job.next_run_at = time.time() + job.interval_seconds
        events.publish("job_resumed", {"job_id": job_id, "name": job.name})
        return True

    def trigger_now(self, job_id: str) -> JobExecutionRecord:
        """Execute a scheduled job immediately."""
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")
        if job.status == "CANCELLED":
            raise ValueError(f"Cannot trigger cancelled job '{job_id}'.")

        now = time.time()
        exec_id = f"exec_{uuid.uuid4().hex[:10]}"
        record = JobExecutionRecord(
            execution_id=exec_id,
            job_id=job.id,
            status="RUNNING",
            started_at=now,
        )

        handler = self._action_handlers.get(job.target_action)
        try:
            if handler:
                res = handler(job.payload)
            else:
                res = {"status": "ok", "action": job.target_action}

            record.status = "COMPLETED"
            record.output = res
            record.finished_at = time.time()
            job.total_runs += 1
            job.consecutive_failures = 0
            job.last_run_at = record.finished_at
            job.next_run_at = record.finished_at + job.interval_seconds
            events.publish("job_executed", {"job_id": job.id, "execution_id": exec_id, "status": "COMPLETED"})
        except Exception as e:
            record.status = "FAILED"
            record.error = str(e)
            record.finished_at = time.time()
            job.total_runs += 1
            job.consecutive_failures += 1
            events.publish("job_failed", {"job_id": job.id, "execution_id": exec_id, "error": str(e)})

        self._history.append(record)
        return record

    def cancel_job(self, job_id: str) -> bool:
        """Cancel and invalidate a scheduled job."""
        job = self.get_job(job_id)
        if not job or job.status == "CANCELLED":
            return False

        job.status = "CANCELLED"
        job.enabled = False
        events.publish("job_cancelled", {"job_id": job_id, "name": job.name})
        return True

    def list_history(self, job_id: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """List historical execution records."""
        records = list(self._history)
        if job_id:
            records = [r for r in records if r.job_id == job_id]
        records.sort(key=lambda r: r.started_at, reverse=True)
        if limit and limit > 0:
            records = records[:limit]
        return [r.to_dict() for r in records]

    def get_stats(self) -> Dict[str, Any]:
        """Aggregate scheduler metrics."""
        total_jobs = len(self._jobs)
        active_jobs = sum(1 for j in self._jobs.values() if j.enabled and j.status == "SCHEDULED")
        paused_jobs = sum(1 for j in self._jobs.values() if j.status == "PAUSED")
        cancelled_jobs = sum(1 for j in self._jobs.values() if j.status == "CANCELLED")

        return {
            "total_jobs": total_jobs,
            "active_jobs": active_jobs,
            "paused_jobs": paused_jobs,
            "cancelled_jobs": cancelled_jobs,
            "total_executions": len(self._history),
        }

    def clear(self) -> None:
        """Clear all jobs and execution history."""
        self._jobs.clear()
        self._history.clear()


# Global scheduler engine instance
scheduler = SchedulerEngine()
