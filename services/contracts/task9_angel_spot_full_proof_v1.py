"""Sanitized per-market Task 9 Angel spot FULL proof."""
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


_MARKET_IDENTITY = {
    "NIFTY": ("NSE", "99926000"),
    "SENSEX": ("BSE", "99919000"),
}


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


class Task9AngelSpotFullProbeStatus(
    str,
    Enum,
):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    MALFORMED = "MALFORMED"


@dataclass(frozen=True, slots=True)
class Task9AngelSpotFullProofV1:
    SCHEMA_VERSION: ClassVar[str] = (
        "task9_angel_spot_full_proof.v1"
    )

    proof_id: str
    observed_at: datetime

    market: str
    exchange: str
    token: str

    status: Task9AngelSpotFullProbeStatus

    provider_timestamp: datetime | None
    ltp: float | None

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

        if market not in _MARKET_IDENTITY:
            raise ValueError("market")

        object.__setattr__(
            self,
            "market",
            market,
        )

        exchange = _text(
            self.exchange,
            "exchange",
        ).upper()

        token = _text(
            self.token,
            "token",
        )

        object.__setattr__(
            self,
            "exchange",
            exchange,
        )
        object.__setattr__(
            self,
            "token",
            token,
        )

        expected_exchange, expected_token = (
            _MARKET_IDENTITY[market]
        )

        if (
            exchange != expected_exchange
            or token != expected_token
        ):
            raise ValueError(
                "spot market identity"
            )

        try:
            object.__setattr__(
                self,
                "status",
                Task9AngelSpotFullProbeStatus(
                    self.status
                ),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("status") from exc

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
            is Task9AngelSpotFullProbeStatus.AVAILABLE
        ):
            if self.provider_timestamp is None:
                raise ValueError(
                    "AVAILABLE requires provider timestamp"
                )

            if self.ltp is None:
                raise ValueError(
                    "AVAILABLE requires LTP"
                )

            if self.sanitized_reason is not None:
                raise ValueError(
                    "AVAILABLE cannot contain failure reason"
                )

        else:
            if self.sanitized_reason is None:
                raise ValueError(
                    "failed spot proof requires reason"
                )

        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError(
                "Task9 spot FULL proof must remain PAPER-only"
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
            "token": self.token,
            "status": self.status.value,
            "provider_timestamp": (
                None
                if self.provider_timestamp is None
                else self.provider_timestamp.isoformat()
            ),
            "ltp": self.ltp,
            "identity_verified": (
                self.identity_verified
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
