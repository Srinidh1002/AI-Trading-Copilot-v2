from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Mapping

from services.contracts.market_session_validation_v1 import (
    MarketSessionValidationV1,
)
from services.contracts.paper_orchestration_policy_v1 import (
    PaperOrchestrationPolicyV1,
)


def _aware(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True, slots=True)
class PaperOrchestrationCycleInputV1:
    cycle_id: str
    cycle_idempotency_key: str
    observation_id: str
    orchestration_policy: PaperOrchestrationPolicyV1
    underlying_symbol: str
    exchange: str
    trading_day_id: str
    market_timestamp: datetime
    received_at: datetime
    cycle_requested_at: datetime
    session_validation: MarketSessionValidationV1
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
    analysis_result: object | None = None
    trade_opportunity: object | None = None
    integrated_trade_plan_result: object | None = None
    p7_persistence_snapshot: object | None = None
    p8_persistence_snapshot: object | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = "paper_orchestration_cycle_input.v1"

    def __post_init__(self) -> None:
        if self.schema_version != "paper_orchestration_cycle_input.v1":
            raise ValueError("unsupported schema_version")

        for name in (
            "cycle_id",
            "cycle_idempotency_key",
            "observation_id",
            "trading_day_id",
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
            object.__setattr__(self, name, _text(getattr(self, name), name))

        if not isinstance(self.orchestration_policy, PaperOrchestrationPolicyV1):
            raise TypeError(
                "orchestration_policy must be a PaperOrchestrationPolicyV1"
            )
        if not isinstance(self.session_validation, MarketSessionValidationV1):
            raise TypeError(
                "session_validation must be a MarketSessionValidationV1"
            )

        symbol = _text(self.underlying_symbol, "underlying_symbol").upper()
        exchange = _text(self.exchange, "exchange").upper()
        if symbol not in self.orchestration_policy.supported_instruments:
            raise ValueError("underlying_symbol is unsupported")
        if exchange not in self.orchestration_policy.supported_exchanges:
            raise ValueError("exchange is unsupported")
        object.__setattr__(self, "underlying_symbol", symbol)
        object.__setattr__(self, "exchange", exchange)

        market_timestamp = _aware(self.market_timestamp, "market_timestamp")
        received_at = _aware(self.received_at, "received_at")
        requested_at = _aware(self.cycle_requested_at, "cycle_requested_at")

        if received_at < market_timestamp:
            raise ValueError("received_at cannot precede market_timestamp")
        if requested_at < received_at:
            raise ValueError("cycle_requested_at cannot precede received_at")

        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.orchestration_policy.execution_mode != "PAPER":
            raise ValueError("orchestration_policy must be PAPER-only")
        if self.orchestration_policy.live_execution_eligible:
            raise ValueError("live execution is not eligible")

        if (
            self.session_validation.symbol != symbol
            or self.session_validation.exchange != exchange
        ):
            raise ValueError("session_validation market identity mismatch")
        if self.session_validation.market_timestamp != market_timestamp:
            raise ValueError("session_validation timestamp mismatch")

        expected_day = market_timestamp.date().isoformat()
        if self.trading_day_id != expected_day:
            raise ValueError(
                "trading_day_id must equal market_timestamp date"
            )

        age_seconds = (requested_at - market_timestamp).total_seconds()
        if age_seconds > self.orchestration_policy.maximum_observation_age_seconds:
            raise ValueError("market observation is stale")
        if (
            age_seconds
            < -self.orchestration_policy.maximum_future_skew_seconds
        ):
            raise ValueError("market observation exceeds future skew")

        object.__setattr__(self, "metadata", dict(self.metadata))

    @staticmethod
    def _source_identity(value: object | None) -> dict[str, Any] | None:
        if value is None:
            return None

        result_type = type(value).__name__
        candidate_ids = (
            "result_id",
            "opportunity_id",
            "integration_id",
            "paper_trade_id",
            "portfolio_id",
            "snapshot_id",
            "decision_id",
        )
        result_id = None
        for name in candidate_ids:
            item = getattr(value, name, None)
            if item is not None:
                result_id = str(item)
                break

        semantic_hash = None
        semantic_hash_method = getattr(value, "semantic_hash", None)
        if callable(semantic_hash_method):
            semantic_hash = str(semantic_hash_method())
        else:
            to_json = getattr(value, "to_json", None)
            if callable(to_json):
                payload = to_json()
                semantic_hash = hashlib.sha256(
                    payload.encode("utf-8")
                ).hexdigest()

        return {
            "type": result_type,
            "id": result_id,
            "semantic_hash": semantic_hash,
        }

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "cycle_idempotency_key": self.cycle_idempotency_key,
            "observation_id": self.observation_id,
            "orchestration_policy_id": (
                self.orchestration_policy.orchestration_policy_id
            ),
            "underlying_symbol": self.underlying_symbol,
            "exchange": self.exchange,
            "trading_day_id": self.trading_day_id,
            "market_timestamp": self.market_timestamp.isoformat(),
            "received_at": self.received_at.isoformat(),
            "session_validation_id": self.session_validation.validation_id,
            "p6_integration_id": self.p6_integration_id,
            "p8_admission_request_id": self.p8_admission_request_id,
            "p8_admission_idempotency_key": (
                self.p8_admission_idempotency_key
            ),
            "p8_portfolio_event_id": self.p8_portfolio_event_id,
            "p7_requested_transition_id": self.p7_requested_transition_id,
            "p7_position_id": self.p7_position_id,
            "p7_entry_fill_id": self.p7_entry_fill_id,
            "p8_update_idempotency_key": self.p8_update_idempotency_key,
            "p8_update_event_id": self.p8_update_event_id,
            "execution_mode": self.execution_mode,
            "analysis_result": self._source_identity(self.analysis_result),
            "trade_opportunity": self._source_identity(
                self.trade_opportunity
            ),
            "integrated_trade_plan_result": self._source_identity(
                self.integrated_trade_plan_result
            ),
            "p7_persistence_snapshot": self._source_identity(
                self.p7_persistence_snapshot
            ),
            "p8_persistence_snapshot": self._source_identity(
                self.p8_persistence_snapshot
            ),
            "metadata": dict(sorted(self.metadata.items())),
            "schema_version": self.schema_version,
        }

    def semantic_hash(self) -> str:
        payload = json.dumps(
            self.semantic_dict(),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        result = self.semantic_dict()
        result.update(
            {
                "cycle_id": self.cycle_id,
                "cycle_requested_at": self.cycle_requested_at.isoformat(),
            }
        )
        return result

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
        )
