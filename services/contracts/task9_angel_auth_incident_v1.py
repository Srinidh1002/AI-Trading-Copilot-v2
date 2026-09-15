"""Sanitized, non-secret Task 9 Angel auth incident evidence."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import ClassVar


_SECRET_TERMS = (
    "api_key",
    "apikey",
    "password",
    "secret",
    "authorization",
    "totp",
    "jwt",
    "refresh",
    "feed_token",
    "access_token",
    "client_id",
    "pin",
    "cookie",
    "raw_payload",
    "provider_payload",
    "raw_exception",
    "exception_text",
)


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(name)

    cleaned = value.strip()

    if any(
        term in cleaned.lower()
        for term in _SECRET_TERMS
    ):
        raise ValueError(
            f"{name} contains secret-like material"
        )

    return cleaned


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)

    return value


class Task9AngelAuthIncidentSeverity(
    str,
    Enum,
):
    BLOCKED_RETRYABLE = "BLOCKED_RETRYABLE"
    FAILED_FATAL = "FAILED_FATAL"


@dataclass(frozen=True, slots=True)
class Task9AngelAuthIncidentV1:
    SCHEMA_VERSION: ClassVar[str] = (
        "task9_angel_auth_incident.v1"
    )

    incident_id: str
    proof_id: str
    observed_at: datetime

    severity: Task9AngelAuthIncidentSeverity

    reason_code: str

    provider_code: str | None = None
    sanitized_reason: str | None = None

    provider_family: str = "ANGEL_AUTH_SESSION"
    capability: str = "AUTH_SESSION"

    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "incident_id",
            "proof_id",
            "reason_code",
            "provider_family",
            "capability",
        ):
            object.__setattr__(
                self,
                name,
                _text(
                    getattr(self, name),
                    name,
                ),
            )

        _aware(
            self.observed_at,
            "observed_at",
        )

        try:
            object.__setattr__(
                self,
                "severity",
                Task9AngelAuthIncidentSeverity(
                    self.severity
                ),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "severity"
            ) from exc

        if self.provider_code is not None:
            code = _text(
                self.provider_code,
                "provider_code",
            ).upper()

            if not (
                code.startswith("AG")
                or code.startswith("AB")
            ):
                raise ValueError(
                    "provider_code"
                )

            object.__setattr__(
                self,
                "provider_code",
                code,
            )

        if self.sanitized_reason is not None:
            object.__setattr__(
                self,
                "sanitized_reason",
                _text(
                    self.sanitized_reason,
                    "sanitized_reason",
                ),
            )

        if (
            self.provider_family
            != "ANGEL_AUTH_SESSION"
            or self.capability
            != "AUTH_SESSION"
        ):
            raise ValueError(
                "Angel auth incident identity"
            )

        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError(
                "Task9 Angel auth incident must remain PAPER-only"
            )

        if self.schema_version != self.SCHEMA_VERSION:
            raise ValueError(
                "schema_version"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "incident_id": self.incident_id,
            "proof_id": self.proof_id,
            "observed_at": (
                self.observed_at.isoformat()
            ),
            "severity": self.severity.value,
            "reason_code": self.reason_code,
            "provider_code": self.provider_code,
            "sanitized_reason": (
                self.sanitized_reason
            ),
            "provider_family": (
                self.provider_family
            ),
            "capability": self.capability,
            "execution_mode": (
                self.execution_mode
            ),
            "broker_order_submission": (
                self.broker_order_submission
            ),
            "live_execution_eligible": (
                self.live_execution_eligible
            ),
        }
