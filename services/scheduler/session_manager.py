"""
Session Manager

Controls trading session state for the
AI Trading Copilot.

Responsibilities
----------------
✓ Session Lifecycle
✓ Login/Logout State
✓ Active Session Tracking
✓ Session Timeout
✓ Session Summary
✓ Session Validation
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


class SessionManager:

    def __init__(
        self,
        timeout_minutes: int = 30,
    ):

        self.timeout = timedelta(
            minutes=timeout_minutes
        )

        self.active = False

        self.user: str | None = None

        self.session_start: datetime | None = None

        self.last_activity: datetime | None = None

        self.metadata: dict[str, Any] = {}

    # --------------------------------------------------

    def start(
        self,
        user: str,
        metadata: dict[str, Any] | None = None,
    ):

        now = datetime.now()

        self.active = True

        self.user = user

        self.session_start = now

        self.last_activity = now

        self.metadata = metadata or {}

    # --------------------------------------------------

    def touch(self):

        if self.active:

            self.last_activity = datetime.now()

    # --------------------------------------------------

    def is_expired(self) -> bool:

        if not self.active:

            return True

        if self.last_activity is None:

            return True

        return (

            datetime.now()

            - self.last_activity

        ) > self.timeout

    # --------------------------------------------------

    def validate(self) -> bool:

        if not self.active:

            return False

        if self.is_expired():

            self.end()

            return False

        self.touch()

        return True

    # --------------------------------------------------

    def end(self):

        self.active = False

        self.user = None

        self.session_start = None

        self.last_activity = None

        self.metadata.clear()

    # --------------------------------------------------

    def duration(self) -> int:

        if (

            not self.active

            or self.session_start is None

        ):

            return 0

        return int(

            (

                datetime.now()

                - self.session_start

            ).total_seconds()

        )

    # --------------------------------------------------

    def summary(self):

        return {

            "active": self.active,

            "user": self.user,

            "session_duration_seconds": self.duration(),

            "expired": self.is_expired(),

            "last_activity": (

                self.last_activity.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

                if self.last_activity

                else None

            ),

            "metadata": self.metadata,

        }

    # --------------------------------------------------

    def get_metadata(
        self,
        key: str,
        default: Any = None,
    ) -> Any:

        return self.metadata.get(
            key,
            default,
        )

    # --------------------------------------------------

    def set_metadata(
        self,
        key: str,
        value: Any,
    ):

        self.metadata[key] = value