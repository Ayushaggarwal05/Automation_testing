"""
Core API service handling mock endpoints and routing logic.
"""

from typing import Dict, Any, Optional, List
try:
    from auth import AuthService
    from events import events
    from storage import InMemoryStorage, BaseStorage
    from middleware import MiddlewarePipeline, RequestContext
    from cache import CacheManager
    from metrics import metrics
    from task_queue import task_queue
    from webhooks import webhooks
    from plugins import plugins
    from notifications import notifications
    from workflows import workflows
    from audit import audit_logger
    from feature_flags import feature_flags
    from resilience import resilience
    from vault import vault
    from scheduler import scheduler
except ImportError:
    from src.auth import AuthService
    from src.events import events
    from src.storage import InMemoryStorage, BaseStorage
    from src.middleware import MiddlewarePipeline, RequestContext
    from src.cache import CacheManager
    from src.metrics import metrics
    from src.task_queue import task_queue
    from src.webhooks import webhooks
    from src.plugins import plugins
    from src.notifications import notifications
    from src.workflows import workflows
    from src.audit import audit_logger
    from src.feature_flags import feature_flags
    from src.resilience import resilience
    from src.vault import vault
    from src.scheduler import scheduler


class APIService:
    def __init__(self, storage: Optional[BaseStorage] = None, cache: Optional[CacheManager] = None):
        self.auth_service = AuthService()
        self.events = events
        self.middleware = MiddlewarePipeline()
        self.cache = cache or CacheManager(default_ttl=300)
        self.metrics = metrics
        self.task_queue = task_queue
        self.webhooks = webhooks
        self.plugins = plugins
        self.notifications = notifications
        self.workflows = workflows
        self.audit = audit_logger
        self.flags = feature_flags
        self.resilience = resilience
        self.vault = vault
        self.scheduler = scheduler
        self.storage: BaseStorage = storage or InMemoryStorage(
            initial_data=[
                {"id": 1, "name": "Item Alpha", "status": "active"},
                {"id": 2, "name": "Item Beta", "status": "pending"},
            ]
        )

    @property
    def data_store(self) -> Dict[str, Any]:
        """Backwards-compatible interface for accessing stored items."""
        return {"items": self.storage.get_all()}

    def health_check(self) -> Dict[str, str]:
        """Simple health check endpoint."""
        self.metrics.record_request("/health", 1.0, 200)
        return {"status": "ok", "service": "automation-api", "version": "2.4.0"}

    def list_plugins(self, token: str) -> Dict[str, Any]:
        """List all active extensions and plugins if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}
        return {"plugins": self.plugins.list_plugins(), "status_code": 200}

    def register_webhook(self, token: str, event_name: str, target_url: str) -> Dict[str, Any]:
        """Register a webhook subscription if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}
        
        sub = self.webhooks.register(event_name, target_url)
        return {"message": "Webhook registered successfully", "subscription": sub.to_dict(), "status_code": 201}

    def list_webhooks(self, token: str, event_filter: Optional[str] = None) -> Dict[str, Any]:
        """List active webhooks if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}
        
        subs = self.webhooks.list_subscriptions(event_filter)
        return {"subscriptions": subs, "count": len(subs), "status_code": 200}

    def enqueue_job(self, token: str, job_name: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Enqueue a background task if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}
        
        task = self.task_queue.enqueue(task_name=job_name, payload=payload or {})
        return {"message": "Job enqueued", "task": task.to_dict(), "status_code": 202}

    def get_job_status(self, token: str, task_id: str) -> Dict[str, Any]:
        """Check status of an enqueued job if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}
        
        task = self.task_queue.get_task(task_id)
        if not task:
            return {"error": f"Task {task_id} not found", "status_code": 404}
        return {"task": task.to_dict(), "status_code": 200}

    def get_metrics(self, token: str) -> Dict[str, Any]:
        """Retrieve aggregated runtime metrics if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}
        return {"metrics": self.metrics.get_summary(), "status_code": 200}

    def update_item_status(self, token: str, item_id: int, new_status: str) -> Dict[str, Any]:
        """Update an item's status if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        item = self.storage.get_by_id(item_id)
        if not item:
            return {"error": f"Item with id {item_id} not found", "status_code": 404}

        old_status = item.get("status")
        updated_item = self.storage.update(item_id, {"status": new_status})
        self.events.publish("item_status_updated", {"id": item_id, "old_status": old_status, "new_status": new_status})
        return {"message": f"Item {item_id} status updated to {new_status}", "item": updated_item, "status_code": 200}

    def get_audit_events(self, token: str, event_filter: str = "") -> Dict[str, Any]:
        """Retrieve audit log events if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}
        
        logs = self.events.get_audit_log(event_filter)
        return {"events": logs, "count": len(logs), "status_code": 200}

    def get_items(
        self,
        token: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        sort_by: str = "id",
        reverse: bool = False,
    ) -> Dict[str, Any]:
        """Fetch items if authorized, with optional filtering, sorting, and pagination."""
        if not token or not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}
        
        items = self.storage.get_all()
        if status:
            items = [item for item in items if item.get("status") == status]
            
        # Sorting
        if sort_by in ("id", "name", "status"):
            items.sort(key=lambda x: x.get(sort_by, ""), reverse=reverse)

        total_count = len(items)
        # Pagination
        if offset > 0:
            items = items[offset:]
        if limit is not None and limit >= 0:
            items = items[:limit]

        return {
            "data": items,
            "count": len(items),
            "total_count": total_count,
            "offset": offset,
            "limit": limit,
            "status_code": 200,
        }

    def add_item(self, token: str, item_name: str) -> Dict[str, Any]:
        """Add a new item if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}
        
        new_id = self.storage.count() + 1
        new_item = {"id": new_id, "name": item_name, "status": "active"}
        self.storage.add(new_item)
        self.events.publish("item_created", {"id": new_id, "name": item_name})
        return {"message": "Item added successfully", "item": new_item, "status_code": 201}

    def get_item_by_id(self, token: str, item_id: int) -> Dict[str, Any]:
        """Fetch a specific item by ID if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}
        
        item = self.storage.get_by_id(item_id)
        if not item:
            return {"error": f"Item with id {item_id} not found", "status_code": 404}
        return {"data": item, "status_code": 200}

    def search_items(self, token: str, query: str) -> Dict[str, Any]:
        """Search items matching name query if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}
        
        results = [
            item for item in self.storage.get_all()
            if query.lower() in item.get("name", "").lower()
        ]
        return {"query": query, "data": results, "count": len(results), "status_code": 200}

    def batch_add_items(self, token: str, item_names: list) -> Dict[str, Any]:
        """Add multiple items in a single batch operation."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}
        
        added = []
        for name in item_names:
            new_id = self.storage.count() + 1
            item = {"id": new_id, "name": name, "status": "active"}
            self.storage.add(item)
            added.append(item)
        return {"message": f"Successfully added {len(added)} items", "items": added, "status_code": 201}

    def batch_delete_items(self, token: str, item_ids: list) -> Dict[str, Any]:
        """Delete multiple items by ID in a single batch operation."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}
        
        deleted_count = 0
        for item_id in item_ids:
            if self.storage.delete(item_id):
                deleted_count += 1
        return {"message": f"Successfully deleted {deleted_count} items", "deleted_count": deleted_count, "status_code": 200}

    def delete_item(self, token: str, item_id: int) -> Dict[str, Any]:
        """Delete an item by ID if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}
        
        if not self.storage.delete(item_id):
            return {"error": f"Item with id {item_id} not found", "status_code": 404}
        self.events.publish("item_deleted", {"id": item_id})
        return {"message": f"Item {item_id} deleted successfully", "status_code": 200}

    def get_item_summary(self, token: str) -> Dict[str, Any]:
        """Get summary statistics of items grouped by status."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}
        
        items = self.storage.get_all()
        status_counts: Dict[str, int] = {}
        for item in items:
            status = item.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            
        return {
            "total_items": len(items),
            "status_breakdown": status_counts,
            "status_code": 200,
        }

    def batch_update_status(self, token: str, item_ids: List[int], new_status: str) -> Dict[str, Any]:
        """Update status for multiple items in a batch."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}
        
        updated_items = []
        for item_id in item_ids:
            item = self.storage.get_by_id(item_id)
            if item:
                updated = self.storage.update(item_id, {"status": new_status})
                if updated:
                    updated_items.append(updated)
                    self.events.publish("item_status_updated", {"id": item_id, "new_status": new_status})
                    
        return {
            "message": f"Updated status for {len(updated_items)} items",
            "updated_count": len(updated_items),
            "items": updated_items,
            "status_code": 200,
        }

    def export_items(self, token: str, format_type: str = "json") -> Dict[str, Any]:
        """Export all items formatted as json or csv string representation."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}
        
        items = self.storage.get_all()
        if format_type.lower() == "csv":
            csv_lines = ["id,name,status"]
            for item in items:
                csv_lines.append(f"{item.get('id')},{item.get('name')},{item.get('status')}")
            exported_content = "\n".join(csv_lines)
        else:
            exported_content = items

        return {
            "format": format_type,
            "count": len(items),
            "data": exported_content,
            "status_code": 200,
        }

    def clear_items(self, token: str) -> Dict[str, Any]:
        """Remove all items from storage if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}
        
        count = self.storage.count()
        self.storage.clear()
        self.events.publish("items_cleared", {"cleared_count": count})
        return {"message": f"Cleared {count} items", "cleared_count": count, "status_code": 200}

    def send_notification(
        self,
        token: str,
        recipient: str,
        message: str,
        channel: str = "email",
        priority: str = "normal",
        subject: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send a notification through supported channels if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        try:
            notification = self.notifications.send(
                recipient=recipient,
                message=message,
                channel=channel,
                priority=priority,
                subject=subject,
                metadata=metadata,
            )
            return {
                "message": "Notification dispatched successfully",
                "notification": notification.to_dict(),
                "status_code": 201,
            }
        except ValueError as e:
            return {"error": str(e), "status_code": 400}

    def list_notifications(
        self,
        token: str,
        channel: Optional[str] = None,
        status: Optional[str] = None,
        recipient: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """List dispatched notifications with optional filtering if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        notifs = self.notifications.list_notifications(
            channel=channel, status=status, recipient=recipient, limit=limit
        )
        return {"notifications": notifs, "count": len(notifs), "status_code": 200}

    def get_notification(self, token: str, notification_id: str) -> Dict[str, Any]:
        """Retrieve a single notification by ID if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        notif = self.notifications.get_notification(notification_id)
        if not notif:
            return {"error": f"Notification '{notification_id}' not found", "status_code": 404}
        return {"notification": notif.to_dict(), "status_code": 200}

    def cancel_notification(self, token: str, notification_id: str) -> Dict[str, Any]:
        """Cancel a notification if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        cancelled = self.notifications.cancel_notification(notification_id)
        if not cancelled:
            return {
                "error": f"Notification '{notification_id}' could not be cancelled or does not exist",
                "status_code": 404,
            }
        return {"message": f"Notification '{notification_id}' cancelled", "status_code": 200}

    def get_notification_stats(self, token: str) -> Dict[str, Any]:
        """Get aggregate delivery statistics for notifications if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        stats = self.notifications.get_stats()
        return {"stats": stats, "status_code": 200}

    def create_workflow(
        self,
        token: str,
        name: str,
        steps: List[Dict[str, Any]],
        description: str = "",
        trigger_event: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create and register a new automation workflow if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        try:
            workflow = self.workflows.create_workflow(
                name=name,
                steps=steps,
                description=description,
                trigger_event=trigger_event,
            )
            return {
                "message": "Workflow created successfully",
                "workflow": workflow.to_dict(),
                "status_code": 201,
            }
        except ValueError as e:
            return {"error": str(e), "status_code": 400}

    def list_workflows(self, token: str, enabled_only: bool = False) -> Dict[str, Any]:
        """List registered workflows if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        wfs = self.workflows.list_workflows(enabled_only=enabled_only)
        return {"workflows": wfs, "count": len(wfs), "status_code": 200}

    def get_workflow(self, token: str, workflow_id: str) -> Dict[str, Any]:
        """Fetch workflow definition by ID if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        wf = self.workflows.get_workflow(workflow_id)
        if not wf:
            return {"error": f"Workflow '{workflow_id}' not found", "status_code": 404}
        return {"workflow": wf.to_dict(), "status_code": 200}

    def execute_workflow(
        self, token: str, workflow_id: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a workflow pipeline if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        try:
            execution = self.workflows.execute_workflow(workflow_id=workflow_id, context=context)
            return {
                "message": f"Workflow execution finished with status {execution.status}",
                "execution": execution.to_dict(),
                "status_code": 200 if execution.status == "COMPLETED" else 422,
            }
        except ValueError as e:
            return {"error": str(e), "status_code": 404}

    def list_workflow_executions(
        self, token: str, workflow_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """List past workflow execution runs if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        executions = self.workflows.list_executions(workflow_id=workflow_id)
        return {"executions": executions, "count": len(executions), "status_code": 200}

    def get_workflow_execution(self, token: str, execution_id: str) -> Dict[str, Any]:
        """Retrieve execution run details by ID if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        execution = self.workflows.get_execution(execution_id)
        if not execution:
            return {"error": f"Execution '{execution_id}' not found", "status_code": 404}
        return {"execution": execution.to_dict(), "status_code": 200}

    def log_audit_event(
        self,
        token: str,
        actor: str,
        action: str,
        category: str = "DATA_MUTATION",
        severity: str = "INFO",
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Log a cryptographically chained immutable audit event if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        try:
            record = self.audit.record_event(
                actor=actor,
                action=action,
                category=category,
                severity=severity,
                details=details,
            )
            return {
                "message": "Audit event recorded successfully",
                "record": record.to_dict(),
                "status_code": 201,
            }
        except ValueError as e:
            return {"error": str(e), "status_code": 400}

    def query_audit_logs(
        self,
        token: str,
        actor: Optional[str] = None,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Query tamper-evident audit records if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        logs = self.audit.query_logs(
            actor=actor, category=category, severity=severity, limit=limit
        )
        return {"records": logs, "count": len(logs), "status_code": 200}

    def verify_audit_trail(self, token: str) -> Dict[str, Any]:
        """Verify the cryptographic integrity of the entire audit chain."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        result = self.audit.verify_integrity()
        status_code = 200 if result.get("valid") else 409
        return {"integrity": result, "status_code": status_code}

    def export_audit_trail(self, token: str, format_type: str = "json") -> Dict[str, Any]:
        """Export audit logs formatted as JSON or CSV if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        exported = self.audit.export_logs(format_type=format_type)
        return {"export": exported, "status_code": 200}

    def get_audit_stats(self, token: str) -> Dict[str, Any]:
        """Retrieve aggregated audit log statistics if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        stats = self.audit.get_stats()
        return {"stats": stats, "status_code": 200}

    def create_feature_flag(
        self,
        token: str,
        name: str,
        description: str = "",
        enabled: bool = False,
        rollout_percentage: int = 100,
        allowed_roles: Optional[List[str]] = None,
        allowed_users: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new feature flag definition if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        try:
            flag = self.flags.create_flag(
                name=name,
                description=description,
                enabled=enabled,
                rollout_percentage=rollout_percentage,
                allowed_roles=allowed_roles,
                allowed_users=allowed_users,
                metadata=metadata,
            )
            return {
                "message": "Feature flag created successfully",
                "flag": flag.to_dict(),
                "status_code": 201,
            }
        except ValueError as e:
            return {"error": str(e), "status_code": 400}

    def list_feature_flags(self, token: str, enabled_only: bool = False) -> Dict[str, Any]:
        """List registered feature flags if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        flag_list = self.flags.list_flags(enabled_only=enabled_only)
        return {"flags": flag_list, "count": len(flag_list), "status_code": 200}

    def get_feature_flag(self, token: str, name: str) -> Dict[str, Any]:
        """Retrieve a specific feature flag by name if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        flag = self.flags.get_flag(name)
        if not flag:
            return {"error": f"Feature flag '{name}' not found", "status_code": 404}
        return {"flag": flag.to_dict(), "status_code": 200}

    def evaluate_feature_flag(
        self, token: str, name: str, user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Evaluate feature flag state for a user/request context if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        result = self.flags.evaluate(name, user_context=user_context)
        return {"evaluation": result, "status_code": 200}

    def toggle_feature_flag(
        self, token: str, name: str, enabled: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Toggle or update enabled state for a feature flag if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        flag = self.flags.toggle_flag(name, enabled=enabled)
        if not flag:
            return {"error": f"Feature flag '{name}' not found", "status_code": 404}
        return {
            "message": f"Feature flag '{name}' updated",
            "flag": flag.to_dict(),
            "status_code": 200,
        }

    def delete_feature_flag(self, token: str, name: str) -> Dict[str, Any]:
        """Delete a feature flag if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        deleted = self.flags.delete_flag(name)
        if not deleted:
            return {"error": f"Feature flag '{name}' not found", "status_code": 404}
        return {"message": f"Feature flag '{name}' deleted successfully", "status_code": 200}

    def get_feature_flags_stats(self, token: str) -> Dict[str, Any]:
        """Retrieve aggregated feature flags metrics if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        stats = self.flags.get_stats()
        return {"stats": stats, "status_code": 200}

    def create_circuit_breaker(
        self,
        token: str,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
        half_open_success_threshold: int = 2,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Register a new circuit breaker for resilience management if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        try:
            circuit = self.resilience.create_circuit(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout_seconds=recovery_timeout_seconds,
                half_open_success_threshold=half_open_success_threshold,
                metadata=metadata,
            )
            return {
                "message": "Circuit breaker registered successfully",
                "circuit": circuit.to_dict(),
                "status_code": 201,
            }
        except ValueError as e:
            return {"error": str(e), "status_code": 400}

    def list_circuit_breakers(self, token: str) -> Dict[str, Any]:
        """List all circuit breakers and their real-time state if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        circuits = self.resilience.list_circuits()
        return {"circuits": circuits, "count": len(circuits), "status_code": 200}

    def get_circuit_breaker(self, token: str, name: str) -> Dict[str, Any]:
        """Retrieve a specific circuit breaker by name if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        circuit = self.resilience.get_circuit(name)
        if not circuit:
            return {"error": f"Circuit breaker '{name}' not found", "status_code": 404}
        return {"circuit": circuit.to_dict(), "status_code": 200}

    def trip_circuit_breaker(
        self, token: str, name: str, reason: str = "Manual intervention"
    ) -> Dict[str, Any]:
        """Manually trip a circuit breaker to OPEN if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        tripped = self.resilience.trip_circuit(name, reason=reason)
        if not tripped:
            return {"error": f"Circuit breaker '{name}' not found", "status_code": 404}
        return {"message": f"Circuit breaker '{name}' tripped to OPEN", "status_code": 200}

    def reset_circuit_breaker(self, token: str, name: str) -> Dict[str, Any]:
        """Manually reset a circuit breaker to CLOSED if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        reset_ok = self.resilience.reset_circuit(name)
        if not reset_ok:
            return {"error": f"Circuit breaker '{name}' not found", "status_code": 404}
        return {"message": f"Circuit breaker '{name}' reset to CLOSED", "status_code": 200}

    def execute_with_circuit_breaker(
        self,
        token: str,
        name: str,
        action_name: str,
        payload: Optional[Dict[str, Any]] = None,
        fallback_value: Any = None,
    ) -> Dict[str, Any]:
        """Execute protected action through circuit breaker if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        try:
            result = self.resilience.execute(
                name=name, action_name=action_name, payload=payload, fallback_value=fallback_value
            )
            return {"execution": result, "status_code": 200}
        except ValueError as e:
            return {"error": str(e), "status_code": 404}

    def get_resilience_stats(self, token: str) -> Dict[str, Any]:
        """Retrieve aggregated resilience stats if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        stats = self.resilience.get_stats()
        return {"stats": stats, "status_code": 200}

    def store_secret(
        self,
        token: str,
        name: str,
        value: str,
        description: str = "",
        tags: Optional[List[str]] = None,
        ttl_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Store an encrypted secret in the vault if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        try:
            actor = self.auth_service.get_user_from_token(token) or "authorized_user"
            entry = self.vault.store_secret(
                name=name,
                value=value,
                description=description,
                tags=tags,
                ttl_seconds=ttl_seconds,
                actor=actor,
            )
            return {
                "message": "Secret stored securely in vault",
                "secret": entry.to_dict(mask_value=True),
                "status_code": 201,
            }
        except ValueError as e:
            return {"error": str(e), "status_code": 400}

    def get_secret(
        self, token: str, name: str, reveal: bool = False, version: Optional[int] = None
    ) -> Dict[str, Any]:
        """Retrieve a secret by name, with optional plaintext reveal if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        result = self.vault.get_secret(name=name, reveal=reveal, version=version)
        if not result.get("found"):
            return {"error": result.get("error"), "status_code": 404}
        return {"secret": result, "status_code": 200}

    def rotate_secret(self, token: str, name: str, new_value: str) -> Dict[str, Any]:
        """Rotate an existing secret to a new version if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        try:
            actor = self.auth_service.get_user_from_token(token) or "authorized_user"
            entry = self.vault.rotate_secret(name=name, new_value=new_value, actor=actor)
            return {
                "message": f"Secret '{name}' rotated to version {entry.current_version}",
                "secret": entry.to_dict(mask_value=True),
                "status_code": 200,
            }
        except ValueError as e:
            return {"error": str(e), "status_code": 400}

    def revoke_secret(self, token: str, name: str) -> Dict[str, Any]:
        """Revoke a secret in the vault if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        actor = self.auth_service.get_user_from_token(token) or "authorized_user"
        revoked = self.vault.revoke_secret(name=name, actor=actor)
        if not revoked:
            return {"error": f"Secret '{name}' not found or already revoked", "status_code": 404}
        return {"message": f"Secret '{name}' revoked successfully", "status_code": 200}

    def list_secrets(
        self, token: str, tag_filter: Optional[str] = None, include_revoked: bool = False
    ) -> Dict[str, Any]:
        """List secrets in the vault with masked values if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        secrets_list = self.vault.list_secrets(tag_filter=tag_filter, include_revoked=include_revoked)
        return {"secrets": secrets_list, "count": len(secrets_list), "status_code": 200}

    def get_vault_stats(self, token: str) -> Dict[str, Any]:
        """Retrieve aggregated vault statistics if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        stats = self.vault.get_stats()
        return {"stats": stats, "status_code": 200}

    def schedule_job(
        self,
        token: str,
        name: str,
        target_action: str,
        interval_seconds: int = 60,
        cron_expression: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Schedule a recurring or cron-based background task if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        try:
            job = self.scheduler.schedule_job(
                name=name,
                target_action=target_action,
                interval_seconds=interval_seconds,
                cron_expression=cron_expression,
                payload=payload,
                metadata=metadata,
            )
            return {
                "message": "Job scheduled successfully",
                "job": job.to_dict(),
                "status_code": 201,
            }
        except ValueError as e:
            return {"error": str(e), "status_code": 400}

    def list_scheduled_jobs(self, token: str, enabled_only: bool = False) -> Dict[str, Any]:
        """List scheduled jobs and their execution metadata if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        jobs = self.scheduler.list_jobs(enabled_only=enabled_only)
        return {"jobs": jobs, "count": len(jobs), "status_code": 200}

    def get_scheduled_job(self, token: str, job_id: str) -> Dict[str, Any]:
        """Retrieve a specific scheduled job by ID if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        job = self.scheduler.get_job(job_id)
        if not job:
            return {"error": f"Scheduled job '{job_id}' not found", "status_code": 404}
        return {"job": job.to_dict(), "status_code": 200}

    def pause_scheduled_job(self, token: str, job_id: str) -> Dict[str, Any]:
        """Pause a scheduled job if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        paused = self.scheduler.pause_job(job_id)
        if not paused:
            return {"error": f"Job '{job_id}' could not be paused or not found", "status_code": 404}
        return {"message": f"Job '{job_id}' paused successfully", "status_code": 200}

    def resume_scheduled_job(self, token: str, job_id: str) -> Dict[str, Any]:
        """Resume a paused scheduled job if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        resumed = self.scheduler.resume_job(job_id)
        if not resumed:
            return {"error": f"Job '{job_id}' is not in PAUSED state or not found", "status_code": 404}
        return {"message": f"Job '{job_id}' resumed successfully", "status_code": 200}

    def trigger_scheduled_job(self, token: str, job_id: str) -> Dict[str, Any]:
        """Manually trigger immediate execution of a scheduled job if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        try:
            record = self.scheduler.trigger_now(job_id)
            return {
                "message": f"Job '{job_id}' executed with status {record.status}",
                "execution": record.to_dict(),
                "status_code": 200 if record.status == "COMPLETED" else 422,
            }
        except ValueError as e:
            return {"error": str(e), "status_code": 404}

    def cancel_scheduled_job(self, token: str, job_id: str) -> Dict[str, Any]:
        """Cancel a scheduled job if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        cancelled = self.scheduler.cancel_job(job_id)
        if not cancelled:
            return {"error": f"Job '{job_id}' not found or already cancelled", "status_code": 404}
        return {"message": f"Job '{job_id}' cancelled successfully", "status_code": 200}

    def get_scheduler_stats(self, token: str) -> Dict[str, Any]:
        """Retrieve aggregated scheduler metrics if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}

        stats = self.scheduler.get_stats()
        return {"stats": stats, "status_code": 200}



if __name__ == "__main__":
    api = APIService()
    print("[API] Health:", api.health_check())

    # Generate token and test authorized calls
    auth_token = api.auth_service.generate_token("automation_user")
    print("[API] Get items (Unauthorized):", api.get_items())
    print("[API] Get items (Authorized):", api.get_items(auth_token))
    print("[API] Add item:", api.add_item(auth_token, "Item Gamma"))
    print("[API] Get item by ID:", api.get_item_by_id(auth_token, 1))
    print("[API] Delete item:", api.delete_item(auth_token, 2))

