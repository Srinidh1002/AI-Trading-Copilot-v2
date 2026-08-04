"""Immutable adapter from one two-market parent decision to the PAPER journal."""
from __future__ import annotations

import hashlib
import json
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)
from services.contracts.paper_orchestration_journal_record_v1 import (
    PaperOrchestrationJournalRecordV1,
)
from services.contracts.paper_orchestration_stage_result_v1 import (
    PaperOrchestrationStageResultV1,
)
from services.contracts.two_market_decision_result_v1 import (
    TwoMarketDecisionResultV1,
)
from services.contracts.two_market_parent_cycle_input_v1 import (
    TwoMarketParentCycleInputV1,
)
from services.paper_orchestration.paper_orchestration_journal import (
    PaperOrchestrationJournal,
)


PARENT_CYCLE_JOURNAL_ADAPTER_ID = (
    "TWO_MARKET_PARENT_CYCLE_JOURNAL_ADAPTER_V1"
)


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _json_value(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, Mapping):
        return {
            str(key): _json_value(item)
            for key, item in sorted(
                value.items(),
                key=lambda pair: str(pair[0]),
            )
        }
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, set):
        return sorted(_json_value(item) for item in value)
    if value is None or isinstance(
        value,
        (str, int, float, bool),
    ):
        return value
    raise TypeError(
        f"unsupported journal semantic value: {type(value).__name__}"
    )


def _semantic_payload(
    *,
    parent: TwoMarketParentCycleInputV1,
    decision: TwoMarketDecisionResultV1,
) -> dict[str, Any]:
    return {
        "adapter_id": PARENT_CYCLE_JOURNAL_ADAPTER_ID,
        "parent": _json_value(parent),
        "decision": _json_value(decision),
        "execution_mode": "PAPER",
        "live_execution_eligible": False,
        "broker_order_submission": False,
    }


def parent_cycle_semantic_hash(
    *,
    parent: TwoMarketParentCycleInputV1,
    decision: TwoMarketDecisionResultV1,
) -> str:
    if type(parent) is not TwoMarketParentCycleInputV1:
        raise TypeError("parent")
    if type(decision) is not TwoMarketDecisionResultV1:
        raise TypeError("decision")

    payload = _semantic_payload(
        parent=parent,
        decision=decision,
    )
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_boundary(
    *,
    parent: TwoMarketParentCycleInputV1,
    decision: TwoMarketDecisionResultV1,
) -> None:
    if decision.parent_cycle_id != parent.parent_cycle_id:
        raise ValueError("parent cycle identity mismatch")
    if decision.decision_result_id != parent.decision_result_id:
        raise ValueError("decision result identity mismatch")
    if decision.requested_at != parent.requested_at:
        raise ValueError("parent requested_at mismatch")
    if decision.completed_at != parent.completed_at:
        raise ValueError("parent completed_at mismatch")

    expected_children = (
        (
            parent.nifty_child_result_id,
            parent.nifty_observation_id,
            "NIFTY",
            "NSE",
        ),
        (
            parent.sensex_child_result_id,
            parent.sensex_observation_id,
            "SENSEX",
            "BSE",
        ),
    )
    actual_children = tuple(
        (
            entry.child.child_result_id,
            entry.child.observation_id,
            entry.child.underlying_symbol,
            entry.child.exchange,
        )
        for entry in decision.entries
    )
    if actual_children != expected_children:
        raise ValueError("parent child result boundary mismatch")

    for value, name in (
        (parent.requested_at, "parent.requested_at"),
        (parent.completed_at, "parent.completed_at"),
        (decision.requested_at, "decision.requested_at"),
        (decision.completed_at, "decision.completed_at"),
    ):
        _aware(value, name)

    if (
        parent.execution_mode != "PAPER"
        or parent.live_execution_eligible
        or parent.broker_order_submission
        or decision.execution_mode != "PAPER"
        or decision.live_execution_eligible
        or decision.broker_order_submission
    ):
        raise ValueError("parent journal boundary must remain PAPER-only")


def build_parent_cycle_journal_record(
    *,
    parent: TwoMarketParentCycleInputV1,
    decision: TwoMarketDecisionResultV1,
    persisted_at: datetime,
) -> PaperOrchestrationJournalRecordV1:
    if type(parent) is not TwoMarketParentCycleInputV1:
        raise TypeError("parent")
    if type(decision) is not TwoMarketDecisionResultV1:
        raise TypeError("decision")

    persisted_at = _aware(persisted_at, "persisted_at")
    _validate_boundary(parent=parent, decision=decision)

    semantic_hash = parent_cycle_semantic_hash(
        parent=parent,
        decision=decision,
    )
    key = f"two-market-parent:{parent.parent_cycle_id}"

    stage = PaperOrchestrationStageResultV1(
        stage_result_id=(
            f"{parent.parent_cycle_id}:parent-decision:persisted"
        ),
        cycle_id=parent.parent_cycle_id,
        stage="OPPORTUNITY",
        status="COMPLETED",
        started_at=parent.requested_at,
        completed_at=parent.completed_at,
        source_result_type="TwoMarketDecisionResultV1",
        source_result_id=decision.decision_result_id,
        source_semantic_hash=semantic_hash,
        paper_action_occurred=False,
        blockers=decision.blockers,
        warnings=decision.warnings,
        metadata={
            "adapter_id": PARENT_CYCLE_JOURNAL_ADAPTER_ID,
            "parent_decision": _json_value(decision),
        },
    )

    result = PaperOrchestrationCycleResultV1(
        cycle_result_id=(
            f"{parent.parent_cycle_id}:parent-decision-result"
        ),
        cycle_id=parent.parent_cycle_id,
        cycle_idempotency_key=key,
        cycle_input_semantic_hash=semantic_hash,
        cycle_status="COMPLETED_NO_ACTION",
        terminal_stage="OPPORTUNITY",
        started_at=parent.requested_at,
        completed_at=parent.completed_at,
        stage_results=(stage,),
        blockers=decision.blockers,
        warnings=decision.warnings,
        metadata={
            "adapter_id": PARENT_CYCLE_JOURNAL_ADAPTER_ID,
            "decision_result_id": decision.decision_result_id,
            "decision": decision.decision,
            "selected_market": (
                list(decision.selected_market)
                if decision.selected_market is not None
                else None
            ),
            "selected_candidate_id": decision.selected_candidate_id,
            "timestamp_skew_seconds": decision.timestamp_skew_seconds,
            "broker_order_submission": False,
        },
    )

    return PaperOrchestrationJournalRecordV1(
        journal_record_id=(
            f"{parent.parent_cycle_id}:parent-journal-record"
        ),
        cycle_idempotency_key=key,
        cycle_input_semantic_hash=semantic_hash,
        cycle_result=result,
        persisted_at=persisted_at,
    )


class TwoMarketParentCycleJournalAdapter:
    """Write one exact parent decision through the existing atomic journal."""

    def __init__(
        self,
        *,
        journal: PaperOrchestrationJournal,
        clock,
    ) -> None:
        if type(journal) is not PaperOrchestrationJournal:
            raise TypeError("journal")
        if not callable(clock):
            raise TypeError("clock")
        self.journal = journal
        self.clock = clock

    def persist(
        self,
        *,
        parent: TwoMarketParentCycleInputV1,
        decision: TwoMarketDecisionResultV1,
    ) -> PaperOrchestrationJournalRecordV1:
        persisted_at = _aware(self.clock(), "clock")
        record = build_parent_cycle_journal_record(
            parent=parent,
            decision=decision,
            persisted_at=persisted_at,
        )
        self.journal.save(record)
        return record


