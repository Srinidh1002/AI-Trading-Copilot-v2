from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from services.contracts.market_session_validation_v1 import (
    MarketSessionValidationV1,
)
from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_orchestration_policy_v1 import (
    PaperOrchestrationPolicyV1,
)


_ALLOWED_CYCLE_KINDS = ("OPPORTUNITY", "MONITORING")


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _identity(namespace: str, *parts: object) -> str:
    payload = "|".join(
        (namespace, *(str(item).strip() for item in parts))
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{namespace}-{digest}"


@dataclass(frozen=True, slots=True)
class CertifiedCycleIdentityBundleV1:
    cycle_kind: str
    cycle_id: str
    cycle_idempotency_key: str
    p6_integration_id: str
    p8_admission_request_id: str
    p8_admission_idempotency_key: str
    p8_portfolio_event_id: str
    p7_requested_transition_id: str
    p7_position_id: str
    p7_entry_fill_id: str
    p8_update_idempotency_key: str
    p8_update_event_id: str
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "certified_cycle_identity_bundle.v1"

    def __post_init__(self) -> None:
        kind = _text(self.cycle_kind, "cycle_kind").upper()
        if kind not in _ALLOWED_CYCLE_KINDS:
            raise ValueError("unsupported cycle_kind")
        object.__setattr__(self, "cycle_kind", kind)

        for name in (
            "cycle_id",
            "cycle_idempotency_key",
            "p6_integration_id",
            "p8_admission_request_id",
            "p8_admission_idempotency_key",
            "p8_portfolio_event_id",
            "p7_requested_transition_id",
            "p7_position_id",
            "p7_entry_fill_id",
            "p8_update_idempotency_key",
            "p8_update_event_id",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )

        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible:
            raise ValueError("live execution is not eligible")
        if self.schema_version != "certified_cycle_identity_bundle.v1":
            raise ValueError("unsupported schema_version")


def build_certified_cycle_identities(
    *,
    cycle_kind: str,
    observation_id: str,
    underlying_symbol: str,
    exchange: str,
    market_timestamp: datetime,
) -> CertifiedCycleIdentityBundleV1:
    kind = _text(cycle_kind, "cycle_kind").upper()
    if kind not in _ALLOWED_CYCLE_KINDS:
        raise ValueError("unsupported cycle_kind")

    observation_id = _text(observation_id, "observation_id")
    symbol = _text(underlying_symbol, "underlying_symbol").upper()
    exchange = _text(exchange, "exchange").upper()
    timestamp = _aware(market_timestamp, "market_timestamp")
    trading_day_id = timestamp.date().isoformat()

    basis = (
        kind,
        observation_id,
        symbol,
        exchange,
        trading_day_id,
        timestamp.isoformat(),
    )

    return CertifiedCycleIdentityBundleV1(
        cycle_kind=kind,
        cycle_id=_identity("cycle", *basis),
        cycle_idempotency_key=_identity("cycle-key", *basis),
        p6_integration_id=_identity("p6-integration", *basis),
        p8_admission_request_id=_identity("p8-admission-request", *basis),
        p8_admission_idempotency_key=_identity(
            "p8-admission-key",
            *basis,
        ),
        p8_portfolio_event_id=_identity(
            "p8-admission-event",
            *basis,
        ),
        p7_requested_transition_id=_identity(
            "p7-transition",
            *basis,
        ),
        p7_position_id=_identity("p7-position", *basis),
        p7_entry_fill_id=_identity("p7-entry-fill", *basis),
        p8_update_idempotency_key=_identity("p8-update-key", *basis),
        p8_update_event_id=_identity("p8-update-event", *basis),
    )


def build_certified_cycle_input(
    *,
    cycle_kind: str,
    observation_id: str,
    orchestration_policy: PaperOrchestrationPolicyV1,
    underlying_symbol: str,
    exchange: str,
    market_timestamp: datetime,
    received_at: datetime,
    cycle_requested_at: datetime,
    session_validation: MarketSessionValidationV1,
    analysis_result: object | None = None,
    trade_opportunity: object | None = None,
    integrated_trade_plan_result: object | None = None,
    p7_persistence_snapshot: object | None = None,
    p8_persistence_snapshot: object | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> PaperOrchestrationCycleInputV1:
    if type(orchestration_policy) is not PaperOrchestrationPolicyV1:
        raise TypeError(
            "orchestration_policy must be exact "
            "PaperOrchestrationPolicyV1"
        )
    if type(session_validation) is not MarketSessionValidationV1:
        raise TypeError(
            "session_validation must be exact MarketSessionValidationV1"
        )

    timestamp = _aware(market_timestamp, "market_timestamp")
    received = _aware(received_at, "received_at")
    requested = _aware(cycle_requested_at, "cycle_requested_at")

    identities = build_certified_cycle_identities(
        cycle_kind=cycle_kind,
        observation_id=observation_id,
        underlying_symbol=underlying_symbol,
        exchange=exchange,
        market_timestamp=timestamp,
    )

    supplied_metadata = dict(metadata or {})
    protected = {
        "certified_runtime": True,
        "cycle_kind": identities.cycle_kind,
        "identity_factory_schema": identities.schema_version,
        "broker_order_submission": False,
        "live_execution_eligible": False,
    }
    overlap = set(supplied_metadata).intersection(protected)
    if overlap:
        raise ValueError(
            "metadata cannot override protected keys: "
            + ", ".join(sorted(overlap))
        )
    supplied_metadata.update(protected)

    return PaperOrchestrationCycleInputV1(
        cycle_id=identities.cycle_id,
        cycle_idempotency_key=identities.cycle_idempotency_key,
        observation_id=_text(observation_id, "observation_id"),
        orchestration_policy=orchestration_policy,
        underlying_symbol=_text(
            underlying_symbol,
            "underlying_symbol",
        ).upper(),
        exchange=_text(exchange, "exchange").upper(),
        trading_day_id=timestamp.date().isoformat(),
        market_timestamp=timestamp,
        received_at=received,
        cycle_requested_at=requested,
        session_validation=session_validation,
        p6_integration_id=identities.p6_integration_id,
        p8_admission_request_id=identities.p8_admission_request_id,
        p8_admission_idempotency_key=(
            identities.p8_admission_idempotency_key
        ),
        p8_portfolio_event_id=identities.p8_portfolio_event_id,
        p7_requested_transition_id=(
            identities.p7_requested_transition_id
        ),
        p7_position_id=identities.p7_position_id,
        p7_entry_fill_id=identities.p7_entry_fill_id,
        p8_update_idempotency_key=(
            identities.p8_update_idempotency_key
        ),
        p8_update_event_id=identities.p8_update_event_id,
        execution_mode="PAPER",
        analysis_result=analysis_result,
        trade_opportunity=trade_opportunity,
        integrated_trade_plan_result=integrated_trade_plan_result,
        p7_persistence_snapshot=p7_persistence_snapshot,
        p8_persistence_snapshot=p8_persistence_snapshot,
        metadata=supplied_metadata,
    )
