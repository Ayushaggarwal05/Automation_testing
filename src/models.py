"""
Data models and schema definitions for the Automation Testing application.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any
import time


@dataclass
class ItemModel:
    """Represents an inventory item in the system."""
    id: int
    name: str
    status: str = "active"
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert item model to dictionary representation."""
        return asdict(self)

    def update_status(self, new_status: str) -> None:
        """Update the item status."""
        valid_statuses = {"active", "pending", "archived", "deleted"}
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status: {new_status}. Must be one of {valid_statuses}")
        self.status = new_status


@dataclass
class UserModel:
    """Represents a registered user session."""
    username: str
    role: str = "user"
    token: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    expires_in: int = 3600

    def is_admin(self) -> bool:
        """Check if user has administrative privileges."""
        return self.role == "admin"

    def is_expired(self) -> bool:
        """Check if session is past expiration TTL."""
        return time.time() - self.created_at > self.expires_in

    def to_dict(self) -> Dict[str, Any]:
        """Convert user model to dictionary."""
        return asdict(self)
