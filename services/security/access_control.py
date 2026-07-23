"""
Access Control

Role-based access control (RBAC) for the
AI Trading Copilot.

Responsibilities
----------------
✓ User Registration
✓ Role Assignment
✓ Permission Management
✓ Access Validation
✓ Role Summary
"""

from __future__ import annotations

from typing import Any


class AccessControl:

    DEFAULT_PERMISSIONS = {
        "ADMIN": {
            "trade",
            "paper_trade",
            "backtest",
            "optimize",
            "view_reports",
            "export_reports",
            "manage_users",
            "manage_keys",
            "system_settings",
        },
        "TRADER": {
            "trade",
            "paper_trade",
            "view_reports",
            "export_reports",
        },
        "ANALYST": {
            "backtest",
            "optimize",
            "view_reports",
        },
        "VIEWER": {
            "view_reports",
        },
    }

    def __init__(self):

        self.users: dict[str, dict[str, Any]] = {}

    # --------------------------------------------------

    def register_user(
        self,
        username: str,
        role: str = "VIEWER",
    ):

        role = role.upper()

        if role not in self.DEFAULT_PERMISSIONS:

            raise ValueError(
                f"Unknown role: {role}"
            )

        self.users[username] = {

            "role": role,

            "permissions": set(
                self.DEFAULT_PERMISSIONS[role]
            ),

        }

    # --------------------------------------------------

    def assign_role(
        self,
        username: str,
        role: str,
    ):

        role = role.upper()

        if username not in self.users:

            raise KeyError(username)

        if role not in self.DEFAULT_PERMISSIONS:

            raise ValueError(role)

        self.users[username]["role"] = role

        self.users[username]["permissions"] = set(
            self.DEFAULT_PERMISSIONS[role]
        )

    # --------------------------------------------------

    def grant_permission(
        self,
        username: str,
        permission: str,
    ):

        self.users[username]["permissions"].add(
            permission
        )

    # --------------------------------------------------

    def revoke_permission(
        self,
        username: str,
        permission: str,
    ):

        self.users[username]["permissions"].discard(
            permission
        )

    # --------------------------------------------------

    def has_permission(
        self,
        username: str,
        permission: str,
    ) -> bool:

        if username not in self.users:

            return False

        return (

            permission

            in self.users[username]["permissions"]

        )

    # --------------------------------------------------

    def role(
        self,
        username: str,
    ) -> str | None:

        user = self.users.get(username)

        return None if user is None else user["role"]

    # --------------------------------------------------

    def permissions(
        self,
        username: str,
    ) -> list[str]:

        if username not in self.users:

            return []

        return sorted(

            self.users[username]["permissions"]

        )

    # --------------------------------------------------

    def remove_user(
        self,
        username: str,
    ):

        self.users.pop(
            username,
            None,
        )

    # --------------------------------------------------

    def summary(self):

        return {

            username: {

                "role": info["role"],

                "permissions": sorted(

                    info["permissions"]

                ),

            }

            for username, info

            in self.users.items()

        }

    # --------------------------------------------------

    def clear(self):

        self.users.clear()