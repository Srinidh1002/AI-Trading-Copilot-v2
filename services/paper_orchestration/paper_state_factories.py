from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from services.contracts.paper_market_observation_v1 import (
    PaperMarketObservationV1,
)
from services.contracts.paper_portfolio_policy_v1 import (
    PaperPortfolioPolicyV1,
)
from services.contracts.paper_portfolio_snapshot_v1 import (
    PaperPortfolioSnapshotV1,
)
from services.contracts.paper_trade_entry_evaluation_input_v1 import (
    PaperTradeEntryEvaluationInputV1,
)
from services.contracts.paper_trade_entry_evaluation_result_v1 import (
    PaperTradeEntryEvaluationResultV1,
)
from services.contracts.paper_trade_lifecycle_policy_v1 import (
    PaperTradeLifecyclePolicyV1,
)
from services.contracts.paper_trade_lifecycle_state_v1 import (
    PaperTradeLifecycleStateV1,
)
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)
from services.paper_portfolio.paper_portfolio_aggregation import (
    aggregate_paper_portfolio,
)


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


def build_initial_paper_portfolio_snapshot(
    *,
    portfolio_snapshot_id: str,
    portfolio_id: str,
    policy: PaperPortfolioPolicyV1,
    trading_day_id: str,
    starting_capital: float,
    created_at: datetime,
) -> PaperPortfolioSnapshotV1:
    """Create the canonical empty P8 portfolio through P8 aggregation."""

    if type(policy) is not PaperPortfolioPolicyV1:
        raise TypeError("policy must be an exact PaperPortfolioPolicyV1")

    created_at = _aware(created_at, "created_at")
    return aggregate_paper_portfolio(
        portfolio_snapshot_id=_text(
            portfolio_snapshot_id,
            "portfolio_snapshot_id",
        ),
        portfolio_id=_text(portfolio_id, "portfolio_id"),
        policy=policy,
        trading_day_id=_text(trading_day_id, "trading_day_id"),
        starting_capital=starting_capital,
        reservations=(),
        position_references=(),
        event_sequence=0,
        created_at=created_at,
        updated_at=created_at,
    )


def build_initial_paper_trade_lifecycle_state(
    *,
    lifecycle_state_id: str,
    trade_plan_id: str,
    integrated_trade_plan_result_id: str,
    lifecycle_policy: PaperTradeLifecyclePolicyV1,
    created_at: datetime,
) -> PaperTradeLifecycleStateV1:
    """Create the canonical caller-owned initial P7 PLANNED state."""

    if type(lifecycle_policy) is not PaperTradeLifecyclePolicyV1:
        raise TypeError(
            "lifecycle_policy must be an exact "
            "PaperTradeLifecyclePolicyV1"
        )

    return PaperTradeLifecycleStateV1(
        lifecycle_state_id=_text(
            lifecycle_state_id,
            "lifecycle_state_id",
        ),
        trade_plan_id=_text(trade_plan_id, "trade_plan_id"),
        integrated_trade_plan_result_id=_text(
            integrated_trade_plan_result_id,
            "integrated_trade_plan_result_id",
        ),
        lifecycle_policy_id=lifecycle_policy.lifecycle_policy_id,
        current_state="PLANNED",
        lifecycle_created_at=_aware(created_at, "created_at"),
    )


def _entry_payload_hash(
    *,
    paper_trade_id: str,
    adapter_idempotency_key: str,
    entry_input: PaperTradeEntryEvaluationInputV1,
) -> str:
    payload = {
        "paper_trade_id": paper_trade_id,
        "adapter_idempotency_key": adapter_idempotency_key,
        "operation": "EVALUATE_ENTRY",
        "entry_input": entry_input.semantic_dict(),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_entry_paper_trade_persistence_snapshot(
    *,
    paper_trade_id: str,
    adapter_idempotency_key: str,
    entry_input: PaperTradeEntryEvaluationInputV1,
    entry_result: PaperTradeEntryEvaluationResultV1,
    resulting_lifecycle_state_id: str,
    persisted_at: datetime,
) -> PaperTradePersistenceSnapshotV1:
    """Build durable P7 entry state without invoking a legacy engine."""

    if type(entry_input) is not PaperTradeEntryEvaluationInputV1:
        raise TypeError(
            "entry_input must be an exact "
            "PaperTradeEntryEvaluationInputV1"
        )
    if type(entry_result) is not PaperTradeEntryEvaluationResultV1:
        raise TypeError(
            "entry_result must be an exact "
            "PaperTradeEntryEvaluationResultV1"
        )
    if (
        entry_result.requested_transition_id
        != entry_input.requested_transition_id
    ):
        raise ValueError("entry transition identity mismatch")
    if entry_result.observation_id != entry_input.observation.observation_id:
        raise ValueError("entry observation identity mismatch")

    source = entry_input.lifecycle_state
    persisted_at = _aware(persisted_at, "persisted_at")
    next_state_name = entry_result.resulting_lifecycle_state

    previous_state = source.current_state
    transition_sequence = source.transition_sequence + 1

    # A qualifying entry can be evaluated immediately from PLANNED.
    # Persist the canonical implicit PLANNED -> WAITING_FOR_ENTRY -> OPEN path.
    if (
        source.current_state == "PLANNED"
        and next_state_name == "OPEN"
    ):
        previous_state = "WAITING_FOR_ENTRY"
        transition_sequence = source.transition_sequence + 2

    terminal = next_state_name in {
        "CLOSED_INVALIDATED",
        "CLOSED_SESSION",
        "CLOSED_EXPIRY",
        "BLOCKED",
    }
    state_values: dict[str, Any] = {
        "lifecycle_state_id": _text(
            resulting_lifecycle_state_id,
            "resulting_lifecycle_state_id",
        ),
        "trade_plan_id": source.trade_plan_id,
        "integrated_trade_plan_result_id": (
            source.integrated_trade_plan_result_id
        ),
        "lifecycle_policy_id": source.lifecycle_policy_id,
        "current_state": next_state_name,
        "lifecycle_created_at": source.lifecycle_created_at,
        "previous_state": previous_state,
        "transition_sequence": transition_sequence,
        "last_transition_code": entry_input.requested_transition_id,
        "last_observation_id": entry_input.observation.observation_id,
        "last_observation_timestamp": entry_input.observation.observed_at,
        "is_terminal": terminal,
        "decision_reasons": entry_result.decision_reasons,
        "warnings": entry_result.warnings,
        "metadata": {
            "entry_evaluation_result_id": (
                entry_result.entry_evaluation_result_id
            ),
        },
    }

    if next_state_name == "WAITING_FOR_ENTRY":
        state_values["waiting_for_entry_at"] = persisted_at
    elif next_state_name == "OPEN":
        state_values["opened_at"] = persisted_at
    elif next_state_name.startswith("CLOSED_"):
        state_values["closed_at"] = persisted_at
        state_values["terminal_reason"] = entry_result.entry_decision
    elif next_state_name == "BLOCKED":
        state_values["blocked_at"] = persisted_at
        state_values["terminal_reason"] = "ENTRY_BLOCKED"
        state_values["blockers"] = entry_result.blockers

    lifecycle_state = PaperTradeLifecycleStateV1(**state_values)

    return PaperTradePersistenceSnapshotV1(
        paper_trade_id=_text(paper_trade_id, "paper_trade_id"),
        adapter_idempotency_key=_text(
            adapter_idempotency_key,
            "adapter_idempotency_key",
        ),
        idempotency_payload_hash=_entry_payload_hash(
            paper_trade_id=paper_trade_id,
            adapter_idempotency_key=adapter_idempotency_key,
            entry_input=entry_input,
        ),
        lifecycle_policy=entry_input.lifecycle_policy,
        lifecycle_state=lifecycle_state,
        position=entry_result.position,
        latest_observation=entry_input.observation,
        pnl_evidence=None,
        created_at=source.lifecycle_created_at,
        updated_at=persisted_at,
        event_sequence=lifecycle_state.transition_sequence,
    )
