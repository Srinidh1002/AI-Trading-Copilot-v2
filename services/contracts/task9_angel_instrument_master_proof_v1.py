"""Sanitized Task 9 Angel instrument-master proof contract."""
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


class Task9AngelInstrumentMasterProbeStatus(
    str,
    Enum,
):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    CORRUPT = "CORRUPT"


@dataclass(frozen=True, slots=True)
class Task9AngelInstrumentMasterProofV1:
    SCHEMA_VERSION: ClassVar[str] = (
        "task9_angel_instrument_master_proof.v1"
    )

    proof_id: str
    observed_at: datetime

    status: Task9AngelInstrumentMasterProbeStatus

    fetched_at: datetime | None

    record_count: int | None

    nifty_nfo_identity_present: bool
    sensex_bfo_identity_present: bool

    source_ref: str | None = None
    incident_ref: str | None = None
    sanitized_reason: str | None = None

    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "proof_id",
            _text(
                self.proof_id,
                "proof_id",
            ),
        )

        _aware(
            self.observed_at,
            "observed_at",
        )

        try:
            object.__setattr__(
                self,
                "status",
                Task9AngelInstrumentMasterProbeStatus(
                    self.status
                ),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("status") from exc

        if self.fetched_at is not None:
            _aware(
                self.fetched_at,
                "fetched_at",
            )

            if self.fetched_at > self.observed_at:
                raise ValueError(
                    "fetched_at cannot be in future"
                )

        if self.record_count is not None:
            if (
                type(self.record_count) is not int
                or isinstance(
                    self.record_count,
                    bool,
                )
                or self.record_count < 0
            ):
                raise ValueError(
                    "record_count"
                )

        for name in (
            "nifty_nfo_identity_present",
            "sensex_bfo_identity_present",
        ):
            if type(
                getattr(self, name)
            ) is not bool:
                raise TypeError(name)

        for name in (
            "source_ref",
            "incident_ref",
            "sanitized_reason",
        ):
            value = getattr(
                self,
                name,
            )

            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    _text(
                        value,
                        name,
                    ),
                )

        if (
            self.status
            is Task9AngelInstrumentMasterProbeStatus.AVAILABLE
        ):
            if self.fetched_at is None:
                raise ValueError(
                    "AVAILABLE requires fetched_at"
                )

            if (
                self.record_count is None
                or self.record_count <= 0
            ):
                raise ValueError(
                    "AVAILABLE requires records"
                )

            if self.sanitized_reason is not None:
                raise ValueError(
                    "AVAILABLE cannot contain failure reason"
                )

        if (
            self.status
            is Task9AngelInstrumentMasterProbeStatus.UNAVAILABLE
        ):
            if self.sanitized_reason is None:
                raise ValueError(
                    "UNAVAILABLE requires reason"
                )

        if (
            self.status
            is Task9AngelInstrumentMasterProbeStatus.CORRUPT
        ):
            if self.sanitized_reason is None:
                raise ValueError(
                    "CORRUPT requires reason"
                )

        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError(
                "Task9 instrument master proof must remain PAPER-only"
            )

        if self.schema_version != self.SCHEMA_VERSION:
            raise ValueError(
                "schema_version"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "proof_id": self.proof_id,
            "observed_at": (
                self.observed_at.isoformat()
            ),
            "status": self.status.value,
            "fetched_at": (
                None
                if self.fetched_at is None
                else self.fetched_at.isoformat()
            ),
            "record_count": self.record_count,
            "nifty_nfo_identity_present": (
                self.nifty_nfo_identity_present
            ),
            "sensex_bfo_identity_present": (
                self.sensex_bfo_identity_present
            ),
            "source_ref": self.source_ref,
            "incident_ref": self.incident_ref,
            "sanitized_reason": (
                self.sanitized_reason
            ),
            "execution_mode": self.execution_mode,
            "broker_order_submission": (
                self.broker_order_submission
            ),
            "live_execution_eligible": (
                self.live_execution_eligible
            ),
        }
