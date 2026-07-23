"""
Security Audit

Provides security auditing for the
AI Trading Copilot.

Responsibilities
----------------
✓ Record Security Events
✓ Failed Login Tracking
✓ Permission Changes
✓ API Key Events
✓ Encryption Events
✓ Security Summary
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


class SecurityAudit:

    def __init__(self):

        self.events: list[dict[str, Any]] = []

    # --------------------------------------------------

    def log_event(
        self,
        category: str,
        action: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        event = {

            "timestamp": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

            "category": category.upper(),

            "action": action,

            "details": details or {},

        }

        self.events.append(event)

        return event

    # --------------------------------------------------

    def login_success(
        self,
        username: str,
    ):

        return self.log_event(

            "AUTH",

            "LOGIN_SUCCESS",

            {

                "username": username,

            },

        )

    # --------------------------------------------------

    def login_failure(
        self,
        username: str,
        reason: str,
    ):

        return self.log_event(

            "AUTH",

            "LOGIN_FAILURE",

            {

                "username": username,

                "reason": reason,

            },

        )

    # --------------------------------------------------

    def permission_change(
        self,
        username: str,
        role: str,
    ):

        return self.log_event(

            "ACCESS",

            "ROLE_UPDATED",

            {

                "username": username,

                "role": role,

            },

        )

    # --------------------------------------------------

    def api_key_event(
        self,
        service: str,
        action: str,
    ):

        return self.log_event(

            "API_KEY",

            action.upper(),

            {

                "service": service,

            },

        )

    # --------------------------------------------------

    def credential_event(
        self,
        service: str,
        action: str,
    ):

        return self.log_event(

            "CREDENTIAL",

            action.upper(),

            {

                "service": service,

            },

        )

    # --------------------------------------------------

    def encryption_event(
        self,
        action: str,
    ):

        return self.log_event(

            "ENCRYPTION",

            action.upper(),

        )

    # --------------------------------------------------

    def custom_event(
        self,
        category: str,
        action: str,
        details: dict[str, Any] | None = None,
    ):

        return self.log_event(

            category,

            action,

            details,

        )

    # --------------------------------------------------

    def recent(
        self,
        limit: int = 20,
    ):

        return self.events[-limit:]

    # --------------------------------------------------

    def summary(
        self,
    ):

        categories: dict[str, int] = {}

        for event in self.events:

            category = event["category"]

            categories[category] = (

                categories.get(category, 0) + 1

            )

        return {

            "total_events": len(self.events),

            "categories": categories,

        }

    # --------------------------------------------------

    def clear(
        self,
    ):

        self.events.clear()