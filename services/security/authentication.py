"""
Authentication

Provides authentication services for the
AI Trading Copilot.

Responsibilities
----------------
✓ User Registration
✓ Login
✓ Logout
✓ Password Hashing
✓ Password Verification
✓ Session Token Management
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from typing import Any


class Authentication:

    def __init__(self):

        self.users: dict[str, dict[str, Any]] = {}

        self.sessions: dict[str, str] = {}

    # --------------------------------------------------

    @staticmethod
    def hash_password(
        password: str,
    ) -> str:

        return hashlib.sha256(

            password.encode("utf-8")

        ).hexdigest()

    # --------------------------------------------------

    def register(
        self,
        username: str,
        password: str,
        role: str = "TRADER",
    ) -> bool:

        username = username.lower()

        if username in self.users:

            return False

        self.users[username] = {

            "password": self.hash_password(password),

            "role": role.upper(),

            "created_at": datetime.now(),

        }

        return True

    # --------------------------------------------------

    def authenticate(
        self,
        username: str,
        password: str,
    ) -> bool:

        username = username.lower()

        user = self.users.get(username)

        if user is None:

            return False

        return (

            user["password"]

            == self.hash_password(password)

        )

    # --------------------------------------------------

    def login(
        self,
        username: str,
        password: str,
    ) -> str | None:

        if not self.authenticate(

            username,

            password,

        ):

            return None

        token = secrets.token_hex(32)

        self.sessions[token] = username.lower()

        return token

    # --------------------------------------------------

    def logout(
        self,
        token: str,
    ) -> bool:

        return (

            self.sessions.pop(

                token,

                None,

            )

            is not None

        )

    # --------------------------------------------------

    def validate_token(
        self,
        token: str,
    ) -> bool:

        return token in self.sessions

    # --------------------------------------------------

    def get_user(
        self,
        token: str,
    ) -> dict[str, Any] | None:

        username = self.sessions.get(token)

        if username is None:

            return None

        user = self.users.get(username)

        if user is None:

            return None

        return {

            "username": username,

            "role": user["role"],

            "created_at": user["created_at"],

        }

    # --------------------------------------------------

    def change_password(
        self,
        username: str,
        old_password: str,
        new_password: str,
    ) -> bool:

        username = username.lower()

        if not self.authenticate(

            username,

            old_password,

        ):

            return False

        self.users[username]["password"] = (

            self.hash_password(new_password)

        )

        return True

    # --------------------------------------------------

    def delete_user(
        self,
        username: str,
    ) -> bool:

        username = username.lower()

        if username not in self.users:

            return False

        del self.users[username]

        self.sessions = {

            token: user

            for token, user in self.sessions.items()

            if user != username

        }

        return True

    # --------------------------------------------------

    def active_sessions(self):

        return len(self.sessions)

    # --------------------------------------------------

    def summary(self):

        return {

            "registered_users": len(self.users),

            "active_sessions": len(self.sessions),

        }

    # --------------------------------------------------

    def clear(self):

        self.users.clear()

        self.sessions.clear()