"""
Authentication module providing mock JWT/Token verification and user session handling.
"""

import hashlib
import time
from typing import Optional, Dict, Any


class AuthService:
    def __init__(self, secret_key: str = "super-secret-key"):
        self.secret_key = secret_key
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def generate_token(self, username: str, role: str = "user") -> str:
        """Generate a mock hashed token for the given username and role."""
        raw = f"{username}:{role}:{time.time()}:{self.secret_key}"
        token = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        self._sessions[token] = {
            "username": username,
            "role": role,
            "created_at": time.time(),
            "expires_in": 3600
        }
        return token

    def validate_token(self, token: str) -> bool:
        """Check if token exists and is not expired."""
        session = self._sessions.get(token)
        if not session:
            return False
        if time.time() - session["created_at"] > session["expires_in"]:
            del self._sessions[token]
            return False
        return True

    def get_user_from_token(self, token: str) -> Optional[str]:
        """Retrieve username associated with a valid token."""
        if self.validate_token(token):
            return self._sessions[token]["username"]
        return None

    def get_role_from_token(self, token: str) -> Optional[str]:
        """Retrieve user role associated with a valid token."""
        if self.validate_token(token):
            return self._sessions[token].get("role", "user")
        return None

    def has_role(self, token: str, required_role: str) -> bool:
        """Check if the user with the given token has the required role."""
        return self.get_role_from_token(token) == required_role


if __name__ == "__main__":
    auth = AuthService()
    token = auth.generate_token("tester_admin", role="admin")
    print(f"[Auth] Generated Token: {token}")
    print(f"[Auth] Valid: {auth.validate_token(token)}")
    print(f"[Auth] User: {auth.get_user_from_token(token)}")
    print(f"[Auth] Role: {auth.get_role_from_token(token)}")
    print(f"[Auth] Is Admin: {auth.has_role(token, 'admin')}")
