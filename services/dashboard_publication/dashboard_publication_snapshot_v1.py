from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from .dashboard_publication_envelope_v1 import (
    DashboardPublicationEnvelopeV1,
)


_ATTEMPT_STATUSES = frozenset(
    {
        "NOT_ATTEMPTED",
        "PUBLISHED",
        "DUPLICATE_NO_CHANGE",
        "FAILED_ATTEMPT_PRESERVED",
        "RESET",
    }
)


def _optional_aware(
    value: object,
    name: str,
) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime or None")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _optional_text(
    value: object,
    name: str,
) -> str | None:
    if value is None:
        return None
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a nonblank string or None")
    return value.strip()


@dataclass(frozen=True, slots=True)
class DashboardPublicationSnapshotV1:
    latest_envelope: DashboardPublicationEnvelopeV1 | None
    last_successful_publication_at: datetime | None
    last_attempted_publication_at: datetime | None
    last_attempt_status: str
    last_attempt_error: str | None
    publication_count: int
    failed_attempt_count: int

    execution_mode: ClassVar[str] = "PAPER"
    live_execution_eligible: ClassVar[bool] = False
    schema_version: ClassVar[str] = "dashboard_publication_snapshot.v1"

    def __post_init__(self) -> None:
        if (
            self.latest_envelope is not None
            and type(self.latest_envelope)
            is not DashboardPublicationEnvelopeV1
        ):
            raise TypeError(
                "latest_envelope must be exact "
                "DashboardPublicationEnvelopeV1 or None"
            )

        successful = _optional_aware(
            self.last_successful_publication_at,
            "last_successful_publication_at",
        )
        attempted = _optional_aware(
            self.last_attempted_publication_at,
            "last_attempted_publication_at",
        )
        if (
            successful is not None
            and attempted is not None
            and successful > attempted
        ):
            raise ValueError(
                "last successful publication cannot follow last attempt"
            )
        object.__setattr__(
            self,
            "last_successful_publication_at",
            successful,
        )
        object.__setattr__(
            self,
            "last_attempted_publication_at",
            attempted,
        )

        status = str(self.last_attempt_status).strip().upper()
        if status not in _ATTEMPT_STATUSES:
            raise ValueError("unsupported last_attempt_status")
        object.__setattr__(self, "last_attempt_status", status)

        error = _optional_text(
            self.last_attempt_error,
            "last_attempt_error",
        )
        if status == "FAILED_ATTEMPT_PRESERVED" and error is None:
            raise ValueError(
                "failed attempt status requires last_attempt_error"
            )
        if status != "FAILED_ATTEMPT_PRESERVED" and error is not None:
            raise ValueError(
                "last_attempt_error is only valid for failed attempts"
            )
        object.__setattr__(self, "last_attempt_error", error)

        for name in ("publication_count", "failed_attempt_count"):
            value = getattr(self, name)
            if type(value) is not int or isinstance(value, bool):
                raise TypeError(f"{name} must be an exact int")
            if value < 0:
                raise ValueError(f"{name} must be nonnegative")

        if self.latest_envelope is None:
            if self.publication_count != 0:
                raise ValueError(
                    "empty snapshot must have zero publication_count"
                )
            if self.last_successful_publication_at is not None:
                raise ValueError(
                    "empty snapshot cannot have successful publication time"
                )
        else:
            if self.publication_count <= 0:
                raise ValueError(
                    "published snapshot requires positive publication_count"
                )
            if self.last_successful_publication_at is None:
                raise ValueError(
                    "published snapshot requires successful publication time"
                )
            if (
                self.last_successful_publication_at
                != self.latest_envelope.published_at
            ):
                raise ValueError(
                    "successful publication time must match latest envelope"
                )

        if status == "NOT_ATTEMPTED":
            if self.last_attempted_publication_at is not None:
                raise ValueError(
                    "NOT_ATTEMPTED cannot have attempt time"
                )
            if self.failed_attempt_count != 0:
                raise ValueError(
                    "NOT_ATTEMPTED cannot have failed attempts"
                )

    @classmethod
    def empty(cls) -> "DashboardPublicationSnapshotV1":
        return cls(
            latest_envelope=None,
            last_successful_publication_at=None,
            last_attempted_publication_at=None,
            last_attempt_status="NOT_ATTEMPTED",
            last_attempt_error=None,
            publication_count=0,
            failed_attempt_count=0,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "latest_envelope": (
                self.latest_envelope.to_dict()
                if self.latest_envelope is not None
                else None
            ),
            "last_successful_publication_at": (
                self.last_successful_publication_at.isoformat()
                if self.last_successful_publication_at is not None
                else None
            ),
            "last_attempted_publication_at": (
                self.last_attempted_publication_at.isoformat()
                if self.last_attempted_publication_at is not None
                else None
            ),
            "last_attempt_status": self.last_attempt_status,
            "last_attempt_error": self.last_attempt_error,
            "publication_count": self.publication_count,
            "failed_attempt_count": self.failed_attempt_count,
            "execution_mode": self.execution_mode,
            "live_execution_eligible": self.live_execution_eligible,
            "schema_version": self.schema_version,
        }
