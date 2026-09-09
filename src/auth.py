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

    def generate_token(self, username: str) -> str:
        """Generate a mock hashed token for the given username."""
        raw = f"{username}:{time.time()}:{self.secret_key}"
        token = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        self._sessions[token] = {
            "username": username,
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


if __name__ == "__main__":
    auth = AuthService()
    token = auth.generate_token("tester_admin")
    print(f"[Auth] Generated Token: {token}")
    print(f"[Auth] Valid: {auth.validate_token(token)}")
    print(f"[Auth] User: {auth.get_user_from_token(token)}")
