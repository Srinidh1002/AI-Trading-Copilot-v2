"""Sanitized Task 9 Angel India VIX capability proof."""
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


def _positive(value: object, name: str) -> float:
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or float(value) <= 0
    ):
        raise ValueError(name)

    return float(value)


class Task9AngelIndiaVixProbeStatus(
    str,
    Enum,
):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    MALFORMED = "MALFORMED"


@dataclass(frozen=True, slots=True)
class Task9AngelIndiaVixProofV1:
    SCHEMA_VERSION: ClassVar[str] = (
        "task9_angel_india_vix_proof.v1"
    )

    proof_id: str
    observed_at: datetime

    market: str
    exchange: str
    instrument_type: str

    status: Task9AngelIndiaVixProbeStatus

    provider_timestamp: datetime | None
    ltp: float | None
    previous_close: float | None

    identity_verified: bool

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
            _text(self.proof_id, "proof_id"),
        )

        _aware(
            self.observed_at,
            "observed_at",
        )

        market = _text(
            self.market,
            "market",
        ).upper()

        exchange = _text(
            self.exchange,
            "exchange",
        ).upper()

        instrument_type = _text(
            self.instrument_type,
            "instrument_type",
        ).upper()

        if market != "INDIA_VIX":
            raise ValueError("market")

        if exchange != "NSE":
            raise ValueError("exchange")

        if instrument_type != "AMXIDX":
            raise ValueError(
                "instrument_type"
            )

        object.__setattr__(
            self,
            "market",
            market,
        )
        object.__setattr__(
            self,
            "exchange",
            exchange,
        )
        object.__setattr__(
            self,
            "instrument_type",
            instrument_type,
        )

        try:
            object.__setattr__(
                self,
                "status",
                Task9AngelIndiaVixProbeStatus(
                    self.status
                ),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "status"
            ) from exc

        if type(self.identity_verified) is not bool:
            raise TypeError(
                "identity_verified"
            )

        if self.provider_timestamp is not None:
            _aware(
                self.provider_timestamp,
                "provider_timestamp",
            )

            if (
                self.provider_timestamp
                > self.observed_at
            ):
                raise ValueError(
                    "provider_timestamp cannot be future"
                )

        if self.ltp is not None:
            object.__setattr__(
                self,
                "ltp",
                _positive(
                    self.ltp,
                    "ltp",
                ),
            )

        if self.previous_close is not None:
            object.__setattr__(
                self,
                "previous_close",
                _positive(
                    self.previous_close,
                    "previous_close",
                ),
            )

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
            is Task9AngelIndiaVixProbeStatus.AVAILABLE
        ):
            if self.provider_timestamp is None:
                raise ValueError(
                    "AVAILABLE requires provider timestamp"
                )

            if self.ltp is None:
                raise ValueError(
                    "AVAILABLE requires LTP"
                )

            if self.previous_close is None:
                raise ValueError(
                    "AVAILABLE requires previous close"
                )

            if self.sanitized_reason is not None:
                raise ValueError(
                    "AVAILABLE cannot contain failure reason"
                )

        else:
            if self.sanitized_reason is None:
                raise ValueError(
                    "failed VIX proof requires reason"
                )

        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError(
                "Task9 India VIX proof must remain PAPER-only"
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
            "market": self.market,
            "exchange": self.exchange,
            "instrument_type": (
                self.instrument_type
            ),
            "status": self.status.value,
            "provider_timestamp": (
                None
                if self.provider_timestamp is None
                else self.provider_timestamp.isoformat()
            ),
            "ltp": self.ltp,
            "previous_close": (
                self.previous_close
            ),
            "identity_verified": (
                self.identity_verified
            ),
            "source_ref": self.source_ref,
            "incident_ref": self.incident_ref,
            "sanitized_reason": (
                self.sanitized_reason
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
        }
