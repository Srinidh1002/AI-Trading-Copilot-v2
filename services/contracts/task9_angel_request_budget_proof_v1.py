"""Sanitized Task 9 Angel request-budget capability proof."""
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


class Task9AngelRequestBudgetProbeStatus(
    str,
    Enum,
):
    READY = "READY"
    BLOCKED_RETRYABLE = "BLOCKED_RETRYABLE"
    INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class Task9AngelRequestBudgetProofV1:
    SCHEMA_VERSION: ClassVar[str] = (
        "task9_angel_request_budget_proof.v1"
    )

    proof_id: str
    observed_at: datetime

    status: Task9AngelRequestBudgetProbeStatus

    controller_thread_safe: bool
    account_wide_budget_owner: bool
    endpoint_scoped_cooldowns: bool

    historical_isolated_from_market_data: bool
    historical_isolated_from_greeks: bool

    angel_client_transport_retry_owner: bool
    launcher_next_cycle_retry_only: bool
    launcher_request_burst_owner: bool

    cache_owned_by_controller: bool

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

        try:
            object.__setattr__(
                self,
                "status",
                Task9AngelRequestBudgetProbeStatus(
                    self.status
                ),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("status") from exc

        for name in (
            "controller_thread_safe",
            "account_wide_budget_owner",
            "endpoint_scoped_cooldowns",
            "historical_isolated_from_market_data",
            "historical_isolated_from_greeks",
            "angel_client_transport_retry_owner",
            "launcher_next_cycle_retry_only",
            "launcher_request_burst_owner",
            "cache_owned_by_controller",
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
            value = getattr(self, name)

            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    _text(value, name),
                )

        if (
            self.status
            is Task9AngelRequestBudgetProbeStatus.READY
        ):
            required_true = (
                self.controller_thread_safe,
                self.account_wide_budget_owner,
                self.endpoint_scoped_cooldowns,
                self.historical_isolated_from_market_data,
                self.historical_isolated_from_greeks,
                self.angel_client_transport_retry_owner,
                self.launcher_next_cycle_retry_only,
                self.cache_owned_by_controller,
            )

            if not all(required_true):
                raise ValueError(
                    "READY request budget proof incomplete"
                )

            if self.launcher_request_burst_owner:
                raise ValueError(
                    "launcher must not own request bursts"
                )

            if self.sanitized_reason is not None:
                raise ValueError(
                    "READY cannot contain failure reason"
                )

        else:
            if self.sanitized_reason is None:
                raise ValueError(
                    "non-ready request budget proof requires reason"
                )

        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError(
                "Task9 request-budget proof must remain PAPER-only"
            )

        if self.schema_version != self.SCHEMA_VERSION:
            raise ValueError("schema_version")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "proof_id": self.proof_id,
            "observed_at": (
                self.observed_at.isoformat()
            ),
            "status": self.status.value,
            "controller_thread_safe": (
                self.controller_thread_safe
            ),
            "account_wide_budget_owner": (
                self.account_wide_budget_owner
            ),
            "endpoint_scoped_cooldowns": (
                self.endpoint_scoped_cooldowns
            ),
            "historical_isolated_from_market_data": (
                self.historical_isolated_from_market_data
            ),
            "historical_isolated_from_greeks": (
                self.historical_isolated_from_greeks
            ),
            "angel_client_transport_retry_owner": (
                self.angel_client_transport_retry_owner
            ),
            "launcher_next_cycle_retry_only": (
                self.launcher_next_cycle_retry_only
            ),
            "launcher_request_burst_owner": (
                self.launcher_request_burst_owner
            ),
            "cache_owned_by_controller": (
                self.cache_owned_by_controller
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
