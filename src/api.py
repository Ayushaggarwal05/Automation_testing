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
except ImportError:
    from src.auth import AuthService
    from src.events import events
    from src.storage import InMemoryStorage, BaseStorage
    from src.middleware import MiddlewarePipeline, RequestContext
    from src.cache import CacheManager


class APIService:
    def __init__(self, storage: Optional[BaseStorage] = None, cache: Optional[CacheManager] = None):
        self.auth_service = AuthService()
        self.events = events
        self.middleware = MiddlewarePipeline()
        self.cache = cache or CacheManager(default_ttl=300)
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
        return {"status": "ok", "service": "automation-api", "version": "2.0.0"}

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

