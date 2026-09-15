"""Task 9 durable WebSocket collector runtime proof.

The proof contains no credentials and performs no network work.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Task9WebsocketRuntimeProbeStatus(str, Enum):
    READY = "READY"
    NOT_READY = "NOT_READY"
    INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class Task9WebsocketRuntimeProofV1:
    proof_id: str
    observed_at: datetime
    status: Task9WebsocketRuntimeProbeStatus

    collector_lock_present: bool
    collector_lock_valid: bool

    nifty_tick_received_at: datetime | None
    sensex_tick_received_at: datetime | None

    nifty_provider_timestamp: datetime | None
    sensex_provider_timestamp: datetime | None

    maximum_tick_age_seconds: float

    source_ref: str | None = None
    sanitized_reason: str | None = None

    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    schema_version: str = (
        "task9_websocket_runtime_proof.v1"
    )

    def __post_init__(self) -> None:
        if (
            type(self.proof_id) is not str
            or not self.proof_id.strip()
        ):
            raise ValueError("proof_id")

        if (
            not isinstance(self.observed_at, datetime)
            or self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
        ):
            raise ValueError("observed_at")

        if (
            type(self.maximum_tick_age_seconds)
            not in {int, float}
            or self.maximum_tick_age_seconds <= 0
        ):
            raise ValueError(
                "maximum_tick_age_seconds"
            )

        for name in (
            "nifty_tick_received_at",
            "sensex_tick_received_at",
            "nifty_provider_timestamp",
            "sensex_provider_timestamp",
        ):
            value = getattr(self, name)

            if value is not None and (
                not isinstance(value, datetime)
                or value.tzinfo is None
                or value.utcoffset() is None
            ):
                raise ValueError(name)

        if self.status is Task9WebsocketRuntimeProbeStatus.READY:
            required = (
                self.collector_lock_present,
                self.collector_lock_valid,
                self.nifty_tick_received_at is not None,
                self.sensex_tick_received_at is not None,
                self.nifty_provider_timestamp is not None,
                self.sensex_provider_timestamp is not None,
            )

            if not all(required):
                raise ValueError(
                    "READY WebSocket runtime proof incomplete"
                )

            if self.sanitized_reason is not None:
                raise ValueError(
                    "READY WebSocket proof reason"
                )

        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError(
                "Task 9 WebSocket proof must remain PAPER-only"
            )


__all__ = (
    "Task9WebsocketRuntimeProbeStatus",
    "Task9WebsocketRuntimeProofV1",
)
