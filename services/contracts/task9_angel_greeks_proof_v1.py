"""Sanitized Task 9 Angel option-Greeks capability proof."""
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


def _aware(
    value: object,
    name: str,
) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)

    return value


def _count(
    value: object,
    name: str,
) -> int:
    if (
        type(value) is not int
        or isinstance(value, bool)
        or value < 0
    ):
        raise ValueError(name)

    return value


class Task9AngelGreeksProbeStatus(
    str,
    Enum,
):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True, slots=True)
class Task9AngelGreeksProofV1:
    SCHEMA_VERSION: ClassVar[str] = (
        "task9_angel_greeks_proof.v1"
    )

    proof_id: str
    observed_at: datetime

    market: str
    exchange: str

    status: Task9AngelGreeksProbeStatus

    requested_contract_count: int
    enriched_contract_count: int
    unavailable_contract_count: int

    delta_present: bool
    gamma_present: bool
    theta_present: bool
    vega_present: bool
    implied_volatility_present: bool

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

        exchange = _text(
            self.exchange,
            "exchange",
        ).upper()

        if (market, exchange) not in {
            ("NIFTY", "NFO"),
            ("SENSEX", "BFO"),
        }:
            raise ValueError(
                "Greeks market identity"
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
                Task9AngelGreeksProbeStatus(
                    self.status
                ),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "status"
            ) from exc

        for name in (
            "requested_contract_count",
            "enriched_contract_count",
            "unavailable_contract_count",
        ):
            object.__setattr__(
                self,
                name,
                _count(
                    getattr(self, name),
                    name,
                ),
            )

        if (
            self.enriched_contract_count
            + self.unavailable_contract_count
            != self.requested_contract_count
        ):
            raise ValueError(
                "Greeks contract accounting"
            )

        for name in (
            "delta_present",
            "gamma_present",
            "theta_present",
            "vega_present",
            "implied_volatility_present",
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

        if market == "SENSEX":
            if (
                self.status
                is not Task9AngelGreeksProbeStatus.UNSUPPORTED
            ):
                raise ValueError(
                    "BFO Greeks must remain explicitly unsupported"
                )

            if (
                self.requested_contract_count != 0
                or self.enriched_contract_count != 0
                or self.unavailable_contract_count != 0
            ):
                raise ValueError(
                    "BFO Greeks must not be probed"
                )

            if any((
                self.delta_present,
                self.gamma_present,
                self.theta_present,
                self.vega_present,
                self.implied_volatility_present,
            )):
                raise ValueError(
                    "BFO Greeks must not be fabricated"
                )

        else:
            if (
                self.status
                is Task9AngelGreeksProbeStatus.UNSUPPORTED
            ):
                raise ValueError(
                    "NFO Greeks are documented supported"
                )

            if self.requested_contract_count <= 0:
                raise ValueError(
                    "NFO Greeks proof requires requests"
                )

            if (
                self.status
                is Task9AngelGreeksProbeStatus.AVAILABLE
            ):
                if (
                    self.enriched_contract_count
                    != self.requested_contract_count
                    or self.unavailable_contract_count != 0
                ):
                    raise ValueError(
                        "AVAILABLE requires complete enrichment"
                    )

                if not all((
                    self.delta_present,
                    self.gamma_present,
                    self.theta_present,
                    self.vega_present,
                    self.implied_volatility_present,
                )):
                    raise ValueError(
                        "AVAILABLE requires canonical Greeks fields"
                    )

            elif (
                self.status
                is Task9AngelGreeksProbeStatus.PARTIAL
            ):
                if (
                    self.enriched_contract_count <= 0
                    or self.unavailable_contract_count <= 0
                ):
                    raise ValueError(
                        "PARTIAL Greeks proof"
                    )

            elif (
                self.status
                is Task9AngelGreeksProbeStatus.UNAVAILABLE
            ):
                if self.enriched_contract_count != 0:
                    raise ValueError(
                        "UNAVAILABLE cannot contain enrichment"
                    )

                if self.sanitized_reason is None:
                    raise ValueError(
                        "UNAVAILABLE requires reason"
                    )

        if (
            self.status
            in {
                Task9AngelGreeksProbeStatus.PARTIAL,
                Task9AngelGreeksProbeStatus.UNSUPPORTED,
            }
            and self.sanitized_reason is None
        ):
            raise ValueError(
                "non-complete Greeks proof requires reason"
            )

        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError(
                "Task9 Greeks proof must remain PAPER-only"
            )

        if (
            self.schema_version
            != self.SCHEMA_VERSION
        ):
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
            "status": self.status.value,
            "requested_contract_count": (
                self.requested_contract_count
            ),
            "enriched_contract_count": (
                self.enriched_contract_count
            ),
            "unavailable_contract_count": (
                self.unavailable_contract_count
            ),
            "delta_present": self.delta_present,
            "gamma_present": self.gamma_present,
            "theta_present": self.theta_present,
            "vega_present": self.vega_present,
            "implied_volatility_present": (
                self.implied_volatility_present
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
