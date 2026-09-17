"""Sanitized per-market Task 9 Angel option FULL capability proof."""
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
    "NIFTY": "NFO",
    "SENSEX": "BFO",
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


def _count(value: object, name: str) -> int:
    if (
        type(value) is not int
        or isinstance(value, bool)
        or value < 0
    ):
        raise ValueError(name)

    return value


class Task9AngelOptionFullProbeStatus(
    str,
    Enum,
):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    MALFORMED = "MALFORMED"


@dataclass(frozen=True, slots=True)
class Task9AngelOptionFullProofV1:
    SCHEMA_VERSION: ClassVar[str] = (
        "task9_angel_option_full_proof.v1"
    )

    proof_id: str
    observed_at: datetime

    market: str
    exchange: str

    status: Task9AngelOptionFullProbeStatus

    requested_contract_count: int
    fetched_contract_count: int
    unfetched_contract_count: int
    malformed_contract_count: int

    oldest_provider_timestamp: datetime | None
    newest_provider_timestamp: datetime | None

    exchange_identity_verified: bool

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

        market = _text(
            self.market,
            "market",
        ).upper()

        if market not in _MARKET_IDENTITY:
            raise ValueError("market")

        exchange = _text(
            self.exchange,
            "exchange",
        ).upper()

        if exchange != _MARKET_IDENTITY[market]:
            raise ValueError(
                "option FULL market identity"
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

        try:
            object.__setattr__(
                self,
                "status",
                Task9AngelOptionFullProbeStatus(
                    self.status
                ),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("status") from exc

        for name in (
            "requested_contract_count",
            "fetched_contract_count",
            "unfetched_contract_count",
            "malformed_contract_count",
        ):
            object.__setattr__(
                self,
                name,
                _count(
                    getattr(self, name),
                    name,
                ),
            )

        if self.requested_contract_count <= 0:
            raise ValueError(
                "requested_contract_count"
            )

        if (
            self.fetched_contract_count
            + self.unfetched_contract_count
            + self.malformed_contract_count
            != self.requested_contract_count
        ):
            raise ValueError(
                "option FULL contract accounting"
            )

        if type(
            self.exchange_identity_verified
        ) is not bool:
            raise TypeError(
                "exchange_identity_verified"
            )

        for name in (
            "oldest_provider_timestamp",
            "newest_provider_timestamp",
        ):
            value = getattr(self, name)

            if value is not None:
                _aware(value, name)

                if value > self.observed_at:
                    raise ValueError(
                        f"{name} cannot be future"
                    )

        if (
            self.oldest_provider_timestamp is None
        ) != (
            self.newest_provider_timestamp is None
        ):
            raise ValueError(
                "provider timestamp pair"
            )

        if (
            self.oldest_provider_timestamp is not None
            and self.newest_provider_timestamp is not None
            and self.oldest_provider_timestamp
            > self.newest_provider_timestamp
        ):
            raise ValueError(
                "provider timestamp order"
            )

        if self.fetched_contract_count > 0:
            if (
                self.oldest_provider_timestamp is None
                or self.newest_provider_timestamp is None
            ):
                raise ValueError(
                    "fetched contracts require provider timestamps"
                )
        else:
            if (
                self.oldest_provider_timestamp is not None
                or self.newest_provider_timestamp is not None
            ):
                raise ValueError(
                    "zero fetched contracts cannot have timestamps"
                )

        for name in (
            "source_ref",
            "incident_ref",
            "sanitized_reason",
        ):
            value = getattr(self, name)

            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    _text(value, name),
                )

        if (
            self.status
            is Task9AngelOptionFullProbeStatus.AVAILABLE
        ):
            if (
                self.fetched_contract_count
                != self.requested_contract_count
                or self.unfetched_contract_count != 0
                or self.malformed_contract_count != 0
            ):
                raise ValueError(
                    "AVAILABLE requires complete fetched response"
                )

            if self.sanitized_reason is not None:
                raise ValueError(
                    "AVAILABLE cannot contain failure reason"
                )

        elif (
            self.status
            is Task9AngelOptionFullProbeStatus.PARTIAL
        ):
            if self.fetched_contract_count <= 0:
                raise ValueError(
                    "PARTIAL requires fetched contracts"
                )

            if (
                self.unfetched_contract_count
                + self.malformed_contract_count
                <= 0
            ):
                raise ValueError(
                    "PARTIAL requires rejected contracts"
                )

        elif (
            self.status
            is Task9AngelOptionFullProbeStatus.UNAVAILABLE
        ):
            if self.fetched_contract_count != 0:
                raise ValueError(
                    "UNAVAILABLE cannot contain fetched contracts"
                )

            if self.sanitized_reason is None:
                raise ValueError(
                    "UNAVAILABLE requires reason"
                )

        elif (
            self.status
            is Task9AngelOptionFullProbeStatus.MALFORMED
        ):
            if self.sanitized_reason is None:
                raise ValueError(
                    "MALFORMED requires reason"
                )

        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError(
                "Task9 option FULL proof must remain PAPER-only"
            )

        if self.schema_version != self.SCHEMA_VERSION:
            raise ValueError(
                "schema_version"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "proof_id": self.proof_id,
            "observed_at": self.observed_at.isoformat(),
            "market": self.market,
            "exchange": self.exchange,
            "status": self.status.value,
            "requested_contract_count": (
                self.requested_contract_count
            ),
            "fetched_contract_count": (
                self.fetched_contract_count
            ),
            "unfetched_contract_count": (
                self.unfetched_contract_count
            ),
            "malformed_contract_count": (
                self.malformed_contract_count
            ),
            "oldest_provider_timestamp": (
                None
                if self.oldest_provider_timestamp is None
                else self.oldest_provider_timestamp.isoformat()
            ),
            "newest_provider_timestamp": (
                None
                if self.newest_provider_timestamp is None
                else self.newest_provider_timestamp.isoformat()
            ),
            "exchange_identity_verified": (
                self.exchange_identity_verified
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
