"""
Paper Trading Heartbeat Monitor.

Reads the persisted runtime heartbeat and determines
whether the paper-trading runtime status is fresh or stale.

IMPORTANT:
- PAPER TRADING ONLY.
- READ-ONLY MONITORING.
- NO BROKER CONNECTION.
- NO REAL ORDER PLACEMENT.
"""

from datetime import datetime, timezone

from services.paper_trading_runtime_heartbeat import (
    PaperTradingRuntimeHeartbeat,
)


class PaperTradingHeartbeatMonitor:
    """
    Evaluate persisted runtime heartbeat freshness.
    """

    DEFAULT_MAX_AGE_SECONDS = 180.0

    def __init__(
        self,
        heartbeat=None,
        *,
        max_age_seconds=DEFAULT_MAX_AGE_SECONDS,
        clock=None,
    ):
        self.heartbeat = (
            heartbeat
            if heartbeat is not None
            else PaperTradingRuntimeHeartbeat()
        )

        try:
            self.max_age_seconds = float(
                max_age_seconds
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                "max_age_seconds must be numeric."
            ) from exc

        if self.max_age_seconds <= 0:
            raise ValueError(
                "max_age_seconds must be greater than zero."
            )

        self.clock = (
            clock
            if clock is not None
            else self._utc_now
        )

        if not callable(
            self.clock
        ):
            raise ValueError(
                "clock must be callable."
            )

    @staticmethod
    def _utc_now():
        return datetime.now(
            timezone.utc
        )

    @staticmethod
    def _normalize_datetime(
        value,
    ):
        if not isinstance(
            value,
            datetime,
        ):
            raise ValueError(
                "clock must return a datetime."
            )

        if value.tzinfo is None:
            value = value.replace(
                tzinfo=timezone.utc
            )

        return value.astimezone(
            timezone.utc
        )

    @staticmethod
    def _parse_timestamp(
        value,
    ):
        if not isinstance(
            value,
            str,
        ):
            raise RuntimeError(
                "Runtime heartbeat timestamp is invalid."
            )

        try:
            parsed = datetime.fromisoformat(
                value
            )
        except ValueError as exc:
            raise RuntimeError(
                "Runtime heartbeat timestamp is invalid."
            ) from exc

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(
            timezone.utc
        )

    def check(
        self,
    ):
        """
        Return current heartbeat monitoring status.
        """

        payload = self.heartbeat.read()

        if payload is None:
            return {
                "success": True,
                "status": "MISSING",
                "heartbeat_exists": False,
                "fresh": False,
                "stale": False,
                "age_seconds": None,
                "max_age_seconds": (
                    self.max_age_seconds
                ),
                "heartbeat_at": None,
                "health_snapshot": None,
            }

        heartbeat_at = (
            self._parse_timestamp(
                payload.get(
                    "heartbeat_at"
                )
            )
        )

        now = self._normalize_datetime(
            self.clock()
        )

        age_seconds = max(
            0.0,
            (
                now
                - heartbeat_at
            ).total_seconds(),
        )

        fresh = (
            age_seconds
            <= self.max_age_seconds
        )

        return {
            "success": True,
            "status": (
                "FRESH"
                if fresh
                else "STALE"
            ),
            "heartbeat_exists": True,
            "fresh": fresh,
            "stale": not fresh,
            "age_seconds": age_seconds,
            "max_age_seconds": (
                self.max_age_seconds
            ),
            "heartbeat_at": (
                payload.get(
                    "heartbeat_at"
                )
            ),
            "health_snapshot": (
                payload.get(
                    "health_snapshot"
                )
            ),
        }

    def get_status(
        self,
    ):
        """
        Alias for check().
        """

        return self.check()