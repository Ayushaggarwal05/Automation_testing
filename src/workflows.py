"""
Workflow automation engine for multi-step execution pipelines and event-driven triggers.
"""

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Callable

try:
    from events import events
except ImportError:
    from src.events import events


VALID_ACTIONS = {"notification", "webhook", "status_update", "custom", "event", "log"}
VALID_EXECUTION_STATUSES = {"PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"}


@dataclass
class WorkflowStep:
    """Represents an atomic action step within a workflow pipeline."""
    name: str
    action_type: str
    params: Dict[str, Any] = field(default_factory=dict)
    stop_on_failure: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Workflow:
    """Represents a defined workflow configuration."""
    id: str
    name: str
    description: str = ""
    steps: List[Dict[str, Any]] = field(default_factory=list)
    trigger_event: Optional[str] = None
    enabled: bool = True
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WorkflowExecution:
    """Represents a runtime execution record of a workflow."""
    id: str
    workflow_id: str
    workflow_name: str
    status: str = "PENDING"
    context: Dict[str, Any] = field(default_factory=dict)
    step_results: List[Dict[str, Any]] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class WorkflowEngine:
    """Engine responsible for registering, managing, and executing workflow pipelines."""

    def __init__(self):
        self._workflows: Dict[str, Workflow] = {}
        self._executions: Dict[str, WorkflowExecution] = {}
        self._action_handlers: Dict[str, Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]] = {}
        self._register_default_handlers()

    def _register_default_handlers(self):
        self.register_handler("log", lambda params, ctx: {"status": "ok", "logged": params.get("message", "")})
        self.register_handler("custom", lambda params, ctx: {"status": "ok", "result": params.get("value")})
        self.register_handler("event", lambda params, ctx: {"status": "ok", "event_emitted": params.get("event_name")})
        self.register_handler("notification", lambda params, ctx: {"status": "ok", "dispatched_to": params.get("recipient")})
        self.register_handler("webhook", lambda params, ctx: {"status": "ok", "url": params.get("url")})
        self.register_handler("status_update", lambda params, ctx: {"status": "ok", "new_status": params.get("status")})

    def register_handler(
        self, action_type: str, handler: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]
    ) -> None:
        """Register a custom step action handler."""
        self._action_handlers[action_type] = handler

    def create_workflow(
        self,
        name: str,
        steps: List[Dict[str, Any]],
        description: str = "",
        trigger_event: Optional[str] = None,
    ) -> Workflow:
        """Create and register a new workflow definition."""
        if not name or not name.strip():
            raise ValueError("Workflow name cannot be empty.")
        if not steps or not isinstance(steps, list):
            raise ValueError("Workflow must contain at least one step.")

        # Validate steps
        for step in steps:
            action = step.get("action_type")
            if not action or action not in VALID_ACTIONS:
                raise ValueError(f"Invalid step action_type '{action}'. Supported actions: {sorted(VALID_ACTIONS)}")

        workflow_id = f"wf_{uuid.uuid4().hex[:10]}"
        workflow = Workflow(
            id=workflow_id,
            name=name.strip(),
            description=description.strip(),
            steps=steps,
            trigger_event=trigger_event,
            enabled=True,
            created_at=time.time(),
        )
        self._workflows[workflow_id] = workflow

        events.publish("workflow_created", {"id": workflow_id, "name": name, "steps_count": len(steps)})
        return workflow

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Retrieve workflow definition by ID."""
        return self._workflows.get(workflow_id)

    def list_workflows(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """List all registered workflows."""
        workflows = list(self._workflows.values())
        if enabled_only:
            workflows = [w for w in workflows if w.enabled]
        return [w.to_dict() for w in workflows]

    def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a registered workflow."""
        if workflow_id in self._workflows:
            del self._workflows[workflow_id]
            events.publish("workflow_deleted", {"id": workflow_id})
            return True
        return False

    def execute_workflow(
        self, workflow_id: str, context: Optional[Dict[str, Any]] = None
    ) -> WorkflowExecution:
        """Execute a workflow pipeline synchronously step-by-step."""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow '{workflow_id}' not found.")
        if not workflow.enabled:
            raise ValueError(f"Workflow '{workflow_id}' is disabled.")

        exec_id = f"exec_{uuid.uuid4().hex[:10]}"
        execution = WorkflowExecution(
            id=exec_id,
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            status="RUNNING",
            context=context or {},
            step_results=[],
            started_at=time.time(),
        )
        self._executions[exec_id] = execution
        events.publish("workflow_execution_started", {"execution_id": exec_id, "workflow_id": workflow_id})

        has_failed = False
        for idx, step in enumerate(workflow.steps):
            step_name = step.get("name", f"step_{idx+1}")
            action_type = step.get("action_type")
            params = step.get("params", {})
            stop_on_failure = step.get("stop_on_failure", True)

            try:
                handler = self._action_handlers.get(action_type)
                if handler:
                    result = handler(params, execution.context)
                else:
                    result = {"status": "ok", "message": f"Executed action {action_type}"}

                execution.step_results.append({
                    "step_name": step_name,
                    "action_type": action_type,
                    "status": "COMPLETED",
                    "result": result,
                })
            except Exception as e:
                execution.step_results.append({
                    "step_name": step_name,
                    "action_type": action_type,
                    "status": "FAILED",
                    "error": str(e),
                })
                if stop_on_failure:
                    has_failed = True
                    execution.error_message = f"Step '{step_name}' failed: {str(e)}"
                    break

        execution.completed_at = time.time()
        execution.status = "FAILED" if has_failed else "COMPLETED"
        self._executions[exec_id] = execution

        events.publish(
            "workflow_execution_completed" if not has_failed else "workflow_execution_failed",
            {"execution_id": exec_id, "workflow_id": workflow_id, "status": execution.status},
        )
        return execution

    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Retrieve execution run record by ID."""
        return self._executions.get(execution_id)

    def list_executions(self, workflow_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List execution records with optional filtering by workflow ID."""
        records = list(self._executions.values())
        if workflow_id:
            records = [r for r in records if r.workflow_id == workflow_id]
        records.sort(key=lambda r: r.started_at, reverse=True)
        return [r.to_dict() for r in records]

    def clear(self) -> None:
        """Clear all workflows and execution histories."""
        self._workflows.clear()
        self._executions.clear()


# Global workflow engine instance
workflows = WorkflowEngine()
