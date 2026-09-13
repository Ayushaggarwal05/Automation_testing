"""
Storage and repository layer providing abstract interface and in-memory persistence.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseStorage(ABC):
    """Abstract base repository for items storage."""

    @abstractmethod
    def get_all(self) -> List[Dict[str, Any]]:
        """Retrieve all stored items."""
        pass

    @abstractmethod
    def get_by_id(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a specific item by its primary key ID."""
        pass

    @abstractmethod
    def add(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new item to storage."""
        pass

    @abstractmethod
    def update(self, item_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update fields of an existing item."""
        pass

    @abstractmethod
    def delete(self, item_id: int) -> bool:
        """Delete an item by its ID."""
        pass


class InMemoryStorage(BaseStorage):
    """In-memory thread-safe storage implementation."""

    def __init__(self, initial_data: Optional[List[Dict[str, Any]]] = None):
        self._items: List[Dict[str, Any]] = list(initial_data) if initial_data else []

    def get_all(self) -> List[Dict[str, Any]]:
        return list(self._items)

    def get_by_id(self, item_id: int) -> Optional[Dict[str, Any]]:
        return next((item for item in self._items if item.get("id") == item_id), None)

    def add(self, item: Dict[str, Any]) -> Dict[str, Any]:
        if "id" not in item:
            item["id"] = len(self._items) + 1
        self._items.append(item)
        return item

    def update(self, item_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        item = self.get_by_id(item_id)
        if item:
            item.update(updates)
            return item
        return None

    def delete(self, item_id: int) -> bool:
        initial_len = len(self._items)
        self._items = [item for item in self._items if item.get("id") != item_id]
        return len(self._items) < initial_len

    def count(self) -> int:
        return len(self._items)
