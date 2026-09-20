"""
Utility helper functions for validation, formatting, and logging.
"""

import re
from typing import Dict, Any


def validate_item_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate item payload for creation or updates."""
    if not isinstance(payload, dict):
        return {"valid": False, "error": "Payload must be a dictionary"}
    
    name = payload.get("name")
    if not name or not isinstance(name, str) or not name.strip():
        return {"valid": False, "error": "Item name is required and cannot be empty"}
    
    if len(name.strip()) > 100:
        return {"valid": False, "error": "Item name cannot exceed 100 characters"}

    return {"valid": True, "sanitized_name": name.strip()}


def format_response(status_code: int, data: Any = None, message: str = "") -> Dict[str, Any]:
    """Standardize API response format."""
    response: Dict[str, Any] = {"status_code": status_code}
    if message:
        response["message"] = message
    if data is not None:
        response["data"] = data
    return response


def sanitize_input(text: str) -> str:
    """Strip script blocks, HTML tags, and normalize whitespace."""
    if not text:
        return ""
    # Remove script and style blocks including content
    clean = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Strip any remaining HTML tags
    clean = re.sub(r'<[^>]*>', '', clean)
    return " ".join(clean.split())


def validate_email(email: str) -> bool:
    """Validate standard email format."""
    if not email or not isinstance(email, str):
        return False
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return bool(re.match(pattern, email.strip()))


def generate_slug(text: str) -> str:
    """Generate URL-safe slug from a string."""
    if not text:
        return ""
    # Convert to lowercase and replace non-alphanumeric characters with hyphens
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[-\s]+', '-', slug).strip('-')
    return slug


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate a string to max_length including optional suffix."""
    if not text or len(text) <= max_length:
        return text or ""
    if max_length <= len(suffix):
        return text[:max_length]
    return text[:max_length - len(suffix)] + suffix

