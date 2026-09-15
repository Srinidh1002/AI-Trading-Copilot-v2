"""Task 9 persistence integrity/writability proof contract."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Task9PersistenceProbeStatus(str, Enum):
    READY = "READY"
    BLOCKED_RETRYABLE = "BLOCKED_RETRYABLE"


@dataclass(frozen=True, slots=True)
class Task9PersistenceRootProbeV1:
    root_kind: str
    directory_ready: bool
    exclusive_create_succeeded: bool
    file_fsync_succeeded: bool
    atomic_replace_succeeded: bool
    readback_verified: bool
    cleanup_succeeded: bool

    def __post_init__(self) -> None:
        if self.root_kind not in {
            "PERSISTENCE_ROOT",
            "STARTUP_PREFLIGHT_ROOT",
            "LIVE_STREAM_ROOT",
        }:
            raise ValueError("root_kind")

    @property
    def ready(self) -> bool:
        return all(
            (
                self.directory_ready,
                self.exclusive_create_succeeded,
                self.file_fsync_succeeded,
                self.atomic_replace_succeeded,
                self.readback_verified,
                self.cleanup_succeeded,
            )
        )


@dataclass(frozen=True, slots=True)
class Task9PersistenceWritabilityProofV1:
    proof_id: str
    observed_at: datetime
    status: Task9PersistenceProbeStatus
    roots: tuple[Task9PersistenceRootProbeV1, ...]
    sanitized_reason: str | None = None

    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    schema_version: str = (
        "task9_persistence_writability_proof.v1"
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
            type(self.roots) is not tuple
            or len(self.roots) != 3
        ):
            raise ValueError("roots")

        kinds = {
            item.root_kind
            for item in self.roots
        }

        if kinds != {
            "PERSISTENCE_ROOT",
            "STARTUP_PREFLIGHT_ROOT",
            "LIVE_STREAM_ROOT",
        }:
            raise ValueError("root identities")

        all_ready = all(
            item.ready
            for item in self.roots
        )

        if (
            self.status
            is Task9PersistenceProbeStatus.READY
        ):
            if not all_ready:
                raise ValueError(
                    "READY persistence proof incomplete"
                )

            if self.sanitized_reason is not None:
                raise ValueError(
                    "READY persistence proof reason"
                )

        if (
            self.status
            is Task9PersistenceProbeStatus.BLOCKED_RETRYABLE
            and self.sanitized_reason is None
        ):
            raise ValueError(
                "blocked persistence proof reason"
            )

        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError(
                "Task 9 persistence proof must remain PAPER-only"
            )


__all__ = (
    "Task9PersistenceProbeStatus",
    "Task9PersistenceRootProbeV1",
    "Task9PersistenceWritabilityProofV1",
)
