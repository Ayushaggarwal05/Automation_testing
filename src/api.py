"""
Core API service handling mock endpoints and routing logic.
"""

from typing import Dict, Any, Optional
from auth import AuthService


class APIService:
    def __init__(self):
        self.auth_service = AuthService()
        self.data_store: Dict[str, Any] = {
            "items": [
                {"id": 1, "name": "Item Alpha", "status": "active"},
                {"id": 2, "name": "Item Beta", "status": "pending"},
            ]
        }

    def health_check(self) -> Dict[str, str]:
        """Simple health check endpoint."""
        return {"status": "ok", "service": "automation-api", "version": "1.0.0"}

    def get_items(self, token: Optional[str] = None) -> Dict[str, Any]:
        """Fetch items if authorized."""
        if not token or not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}
        return {"data": self.data_store["items"], "status_code": 200}

    def add_item(self, token: str, item_name: str) -> Dict[str, Any]:
        """Add a new item if authorized."""
        if not self.auth_service.validate_token(token):
            return {"error": "Unauthorized", "status_code": 401}
        
        new_id = len(self.data_store["items"]) + 1
        new_item = {"id": new_id, "name": item_name, "status": "active"}
        self.data_store["items"].append(new_item)
        return {"message": "Item added successfully", "item": new_item, "status_code": 201}


if __name__ == "__main__":
    api = APIService()
    print("[API] Health:", api.health_check())

    # Generate token and test authorized calls
    auth_token = api.auth_service.generate_token("automation_user")
    print("[API] Get items (Unauthorized):", api.get_items())
    print("[API] Get items (Authorized):", api.get_items(auth_token))
    print("[API] Add item:", api.add_item(auth_token, "Item Gamma"))
