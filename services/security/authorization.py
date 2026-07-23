"""
Authorization

Role and permission authorization layer for the
AI Trading Copilot.

Responsibilities
----------------
✓ Role-Based Authorization
✓ Permission Validation
✓ Dynamic Permission Management
✓ Protected Resource Access
✓ Authorization Summary
"""

from __future__ import annotations

from typing import Any

from services.security.access_control import (
    AccessControl,
)


class Authorization:

    def __init__(
        self,
        access_control: AccessControl | None = None,
    ):

        self.access_control = (
            access_control
            if access_control
            else AccessControl()
        )

    # --------------------------------------------------

    def authorize(
        self,
        username: str,
        permission: str,
    ) -> bool:

        return self.access_control.has_permission(
            username,
            permission,
        )

    # --------------------------------------------------

    def require(
        self,
        username: str,
        permission: str,
    ):

        if not self.authorize(
            username,
            permission,
        ):

            raise PermissionError(

                f"User '{username}' "

                f"is not authorized "

                f"for '{permission}'."

            )

    # --------------------------------------------------

    def register_user(
        self,
        username: str,
        role: str = "VIEWER",
    ):

        self.access_control.register_user(
            username,
            role,
        )

    # --------------------------------------------------

    def assign_role(
        self,
        username: str,
        role: str,
    ):

        self.access_control.assign_role(
            username,
            role,
        )

    # --------------------------------------------------

    def grant_permission(
        self,
        username: str,
        permission: str,
    ):

        self.access_control.grant_permission(
            username,
            permission,
        )

    # --------------------------------------------------

    def revoke_permission(
        self,
        username: str,
        permission: str,
    ):

        self.access_control.revoke_permission(
            username,
            permission,
        )

    # --------------------------------------------------

    def role(
        self,
        username: str,
    ) -> str | None:

        return self.access_control.role(
            username,
        )

    # --------------------------------------------------

    def permissions(
        self,
        username: str,
    ) -> list[str]:

        return self.access_control.permissions(
            username,
        )

    # --------------------------------------------------

    def can_trade(
        self,
        username: str,
    ) -> bool:

        return self.authorize(
            username,
            "trade",
        )

    # --------------------------------------------------

    def can_backtest(
        self,
        username: str,
    ) -> bool:

        return self.authorize(
            username,
            "backtest",
        )

    # --------------------------------------------------

    def can_export_reports(
        self,
        username: str,
    ) -> bool:

        return self.authorize(
            username,
            "export_reports",
        )

    # --------------------------------------------------

    def can_manage_system(
        self,
        username: str,
    ) -> bool:

        return self.authorize(
            username,
            "system_settings",
        )

    # --------------------------------------------------

    def summary(self) -> dict[str, Any]:

        return self.access_control.summary()

    # --------------------------------------------------

    def clear(self):

        self.access_control.clear()