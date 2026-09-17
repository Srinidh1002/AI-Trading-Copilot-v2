"""Typed PAPER-only Task 9 collector observability contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Task9CollectorEventType(str, Enum):
    CONNECTED = "CONNECTED"
    SUBSCRIBED = "SUBSCRIBED"
    NO_TICK = "NO_TICK"
    HEARTBEAT = "HEARTBEAT"
    STALE = "STALE"
    DISCONNECTED = "DISCONNECTED"
    RECONNECTING = "RECONNECTING"
    RECONNECTED = "RECONNECTED"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    PARSE_ERROR = "PARSE_ERROR"
    DROPPED_MESSAGE = "DROPPED_MESSAGE"
    SESSION_CLOSE = "SESSION_CLOSE"
    STOPPED = "STOPPED"


@dataclass(frozen=True, slots=True)
class Task9CollectorEventV1:
    event_id: str
    collector_run_id: str
    event_type: Task9CollectorEventType
    observed_at: datetime
    market: str | None = None
    detail_code: str | None = None

    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    schema_version: str = "task9_collector_event.v1"

    def __post_init__(self):
        if (
            type(self.event_id) is not str
            or not self.event_id.strip()
        ):
            raise ValueError("event_id")

        if (
            type(self.collector_run_id) is not str
            or not self.collector_run_id.strip()
        ):
            raise ValueError("collector_run_id")

        object.__setattr__(
            self,
            "event_type",
            Task9CollectorEventType(
                self.event_type
            ),
        )

        if (
            not isinstance(self.observed_at, datetime)
            or self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
        ):
            raise ValueError("observed_at")

        if (
            self.market is not None
            and self.market not in {
                "NIFTY",
                "SENSEX",
            }
        ):
            raise ValueError("market")

        if (
            self.detail_code is not None
            and (
                type(self.detail_code) is not str
                or not self.detail_code.strip()
            )
        ):
            raise ValueError("detail_code")

        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError(
                "collector event must remain PAPER-only"
            )

    def to_dict(self):
        return {
            "event_id": self.event_id,
            "collector_run_id": self.collector_run_id,
            "event_type": self.event_type.value,
            "observed_at": self.observed_at.isoformat(),
            "market": self.market,
            "detail_code": self.detail_code,
            "execution_mode": self.execution_mode,
            "broker_order_submission": (
                self.broker_order_submission
            ),
            "live_execution_eligible": (
                self.live_execution_eligible
            ),
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True, slots=True)
class Task9CollectorRunSummaryV1:
    collector_run_id: str
    started_at: datetime
    stopped_at: datetime

    connected_at: datetime | None

    markets_subscribed: tuple[str, ...]

    nifty_last_tick_received_at: datetime | None
    sensex_last_tick_received_at: datetime | None

    reconnect_count: int
    event_ids: tuple[str, ...]

    close_reason: str
    session_close_state: str

    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    schema_version: str = (
        "task9_collector_run_summary.v1"
    )

    def __post_init__(self):
        if (
            type(self.collector_run_id) is not str
            or not self.collector_run_id.strip()
        ):
            raise ValueError("collector_run_id")

        for name in (
            "started_at",
            "stopped_at",
        ):
            value = getattr(self, name)

            if (
                not isinstance(value, datetime)
                or value.tzinfo is None
                or value.utcoffset() is None
            ):
                raise ValueError(name)

        if self.stopped_at < self.started_at:
            raise ValueError("collector run ordering")

        if self.connected_at is not None:
            if (
                not isinstance(
                    self.connected_at,
                    datetime,
                )
                or self.connected_at.tzinfo is None
                or self.connected_at.utcoffset()
                is None
            ):
                raise ValueError("connected_at")

        for name in (
            "nifty_last_tick_received_at",
            "sensex_last_tick_received_at",
        ):
            value = getattr(self, name)

            if value is not None and (
                not isinstance(value, datetime)
                or value.tzinfo is None
                or value.utcoffset() is None
            ):
                raise ValueError(name)

        if (
            type(self.reconnect_count) is not int
            or self.reconnect_count < 0
        ):
            raise ValueError("reconnect_count")

        if (
            not isinstance(
                self.markets_subscribed,
                tuple,
            )
            or set(self.markets_subscribed)
            - {"NIFTY", "SENSEX"}
        ):
            raise ValueError(
                "markets_subscribed"
            )

        if (
            not isinstance(self.event_ids, tuple)
            or any(
                type(value) is not str
                or not value
                for value in self.event_ids
            )
        ):
            raise ValueError("event_ids")

        if (
            type(self.close_reason) is not str
            or not self.close_reason
        ):
            raise ValueError("close_reason")

        if self.session_close_state not in {
            "NOT_REACHED",
            "SESSION_CLOSED",
            "UNRESOLVED",
        }:
            raise ValueError(
                "session_close_state"
            )

        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError(
                "collector summary must remain PAPER-only"
            )

    def to_dict(self):
        def stamp(value):
            return (
                value.isoformat()
                if value is not None
                else None
            )

        return {
            "collector_run_id": (
                self.collector_run_id
            ),
            "started_at": (
                self.started_at.isoformat()
            ),
            "stopped_at": (
                self.stopped_at.isoformat()
            ),
            "connected_at": (
                stamp(self.connected_at)
            ),
            "markets_subscribed": list(
                self.markets_subscribed
            ),
            "nifty_last_tick_received_at": (
                stamp(
                    self.nifty_last_tick_received_at
                )
            ),
            "sensex_last_tick_received_at": (
                stamp(
                    self.sensex_last_tick_received_at
                )
            ),
            "reconnect_count": (
                self.reconnect_count
            ),
            "event_ids": list(
                self.event_ids
            ),
            "close_reason": (
                self.close_reason
            ),
            "session_close_state": (
                self.session_close_state
            ),
            "execution_mode": (
                self.execution_mode
            ),
            "broker_order_submission": (
                self.broker_order_submission
            ),
            "live_execution_eligible": (
                self.live_execution_eligible
            ),
            "schema_version": (
                self.schema_version
            ),
        }


__all__ = (
    "Task9CollectorEventType",
    "Task9CollectorEventV1",
    "Task9CollectorRunSummaryV1",
)
