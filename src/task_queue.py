"""
Background task queue and job processing engine for async workflow execution.
"""

import time
import uuid
from typing import Dict, Any, Callable, Optional, List
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Task:
    """Represents a discrete executable background task."""

    def __init__(self, task_name: str, payload: Dict[str, Any], handler: Optional[Callable[[Dict[str, Any]], Any]] = None, max_retries: int = 3):
        self.id: str = str(uuid.uuid4())
        self.task_name = task_name
        self.payload = payload
        self.handler = handler
        self.status = TaskStatus.PENDING
        self.result: Optional[Any] = None
        self.error: Optional[str] = None
        self.retries: int = 0
        self.max_retries = max_retries
        self.created_at = time.time()
        self.completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "task_name": self.task_name,
            "status": self.status.value,
            "retries": self.retries,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class TaskQueue:
    """Manages scheduling and processing of background tasks."""

    def __init__(self):
        self._tasks: Dict[str, Task] = {}

    def enqueue(self, task_name: str, payload: Dict[str, Any], handler: Optional[Callable[[Dict[str, Any]], Any]] = None) -> Task:
        """Enqueue a new task for processing."""
        task = Task(task_name=task_name, payload=payload, handler=handler)
        self._tasks[task.id] = task
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Fetch task instance by its UUID."""
        return self._tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task."""
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            task.completed_at = time.time()
            return True
        return False

    def process_next(self) -> Optional[Task]:
        """Process the first pending task in queue."""
        pending_task = next((t for t in self._tasks.values() if t.status == TaskStatus.PENDING), None)
        if not pending_task:
            return None

        pending_task.status = TaskStatus.RUNNING
        try:
            if pending_task.handler:
                pending_task.result = pending_task.handler(pending_task.payload)
            pending_task.status = TaskStatus.COMPLETED
        except Exception as exc:
            pending_task.error = str(exc)
            pending_task.retries += 1
            if pending_task.retries < pending_task.max_retries:
                pending_task.status = TaskStatus.PENDING
            else:
                pending_task.status = TaskStatus.FAILED
        finally:
            pending_task.completed_at = time.time()

        return pending_task

    def process_all(self) -> List[Task]:
        """Process all currently pending tasks until none remain."""
        processed: List[Task] = []
        while True:
            task = self.process_next()
            if not task:
                break
            processed.append(task)
        return processed

    def clear(self) -> None:
        """Clear all tasks from the queue."""
        self._tasks.clear()

    def get_metrics(self) -> Dict[str, int]:
        """Return counts of tasks by status and total count."""
        metrics: Dict[str, int] = {status.value: 0 for status in TaskStatus}
        for task in self._tasks.values():
            metrics[task.status.value] = metrics.get(task.status.value, 0) + 1
        metrics["total"] = len(self._tasks)
        return metrics

    def list_tasks(self, status_filter: Optional[TaskStatus] = None) -> List[Dict[str, Any]]:
        """List tasks with optional status filter."""
        tasks = self._tasks.values()
        if status_filter:
            tasks = [t for t in tasks if t.status == status_filter]
        return [t.to_dict() for t in tasks]


# Global task queue instance
task_queue = TaskQueue()

