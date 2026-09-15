"""PAPER-only Task 9 live-session certification orchestration seam.

The runner deliberately owns scheduling, safety, and count ordering only.
All market reads, PAPER lifecycle work, reconciliation, persistence, and
publication are injected certified authorities; it never submits a broker
order or derives execution truth from dashboard state.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from services.certification.task9_live_paper_trade_counting_evaluator import (
    evaluate_task9_live_paper_trade_counting,
)
from services.contracts.prediction_lifecycle_outcome_record_v1 import (
    PredictionLifecycleOutcomeRecordV1,
)
from services.contracts.prediction_lifecycle_reconciliation_result_v1 import (
    PredictionLifecycleReconciliationResultV1,
)
from services.contracts.prediction_record_v1 import PredictionRecordV1
from services.contracts.task9_live_paper_trade_counting_decision_v1 import (
    Task9LivePaperTradeCountingDecisionV1,
)
from services.contracts.task9_live_paper_trade_counting_input_v1 import (
    Task9LivePaperTradeCountingInputV1,
)
from services.market_session.validator import validate_session_timestamp
from services.contracts.task9_run_classification_v1 import validate_task9_run_classification


_MARKETS = (("NIFTY", "NSE"), ("SENSEX", "BSE"))


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(name)
    return value


@dataclass(frozen=True, slots=True)
class Task9MarketCycleEvidenceV1:
    """Evidence emitted by an injected certified child authority."""
    prediction: PredictionRecordV1
    lifecycle_outcome: PredictionLifecycleOutcomeRecordV1 | None = None
    reconciliation: PredictionLifecycleReconciliationResultV1 | None = None
    terminal_position_closed: bool = False
    record_source: str = "LIVE_REAL_TIME"
    evidence_status: str = "VALID"

    def __post_init__(self) -> None:
        if type(self.prediction) is not PredictionRecordV1:
            raise TypeError("prediction")
        if self.prediction.underlying_symbol not in {"NIFTY", "SENSEX"}:
            raise ValueError("unsupported market")
        if self.lifecycle_outcome is not None and type(self.lifecycle_outcome) is not PredictionLifecycleOutcomeRecordV1:
            raise TypeError("lifecycle_outcome")
        if self.reconciliation is not None and type(self.reconciliation) is not PredictionLifecycleReconciliationResultV1:
            raise TypeError("reconciliation")
        if type(self.terminal_position_closed) is not bool:
            raise TypeError("terminal_position_closed")
        if self.evidence_status not in {"VALID", "DATA_INCIDENT"}:
            raise ValueError("evidence_status")
        if self.evidence_status == "DATA_INCIDENT" and (
            self.lifecycle_outcome is not None
            or self.reconciliation is not None
            or self.terminal_position_closed
        ):
            raise ValueError("data incident cannot carry trade lifecycle evidence")


@dataclass(frozen=True, slots=True)
class Task9InternalChildFailureV1:
    """Sanitized diagnostic evidence for an unexpected child-authority fault."""

    reason_code: str
    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.reason_code) is not str
            or not self.reason_code.startswith("INTERNAL_CHILD_FAILURE_")
        ):
            raise ValueError("reason_code")
        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission
            or self.live_execution_eligible
        ):
            raise ValueError("PAPER-only internal child failure")


@dataclass(frozen=True, slots=True)
class Task9LivePaperCycleResultV1:
    cycle_id: str
    started_at: datetime
    completed_at: datetime
    market_results: tuple[tuple[str, str, Task9LivePaperTradeCountingDecisionV1 | Task9InternalChildFailureV1 | None], ...]
    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.cycle_id, str) or not self.cycle_id.strip():
            raise ValueError("cycle_id")
        if _aware(self.started_at, "started_at") > _aware(self.completed_at, "completed_at"):
            raise ValueError("cycle timestamps")
        if (self.execution_mode != "PAPER" or self.broker_order_submission or self.live_execution_eligible):
            raise ValueError("Task 9 runner must remain PAPER-only")


ChildAuthority = Callable[[str, str, bool], Task9MarketCycleEvidenceV1]
Persist = Callable[[Task9LivePaperCycleResultV1], None]
Publish = Callable[[Task9LivePaperCycleResultV1], None]


class Task9LivePaperCertificationRunner:
    """Run both certification children and count only terminal reconciliation."""
    def __init__(self, *, official_run_id: str, official_start_at: datetime, child_authority: ChildAuthority, persist: Persist, publish: Publish | None = None, run_classification: str = "OFFICIAL_CERTIFICATION") -> None:
        if not isinstance(official_run_id, str) or not official_run_id.strip():
            raise ValueError("official_run_id")
        self.official_run_id = official_run_id.strip()
        self.run_classification = validate_task9_run_classification(run_classification)
        self.official_start_at = _aware(official_start_at, "official_start_at")
        if not callable(child_authority) or not callable(persist) or (publish is not None and not callable(publish)):
            raise TypeError("runner authority")
        self.child_authority, self.persist, self.publish = child_authority, persist, publish

    def run_cycle(self, *, cycle_id: str, evaluated_at: datetime) -> Task9LivePaperCycleResultV1:
        now = _aware(evaluated_at, "evaluated_at")
        if not isinstance(cycle_id, str) or not cycle_id.strip():
            raise ValueError("cycle_id")
        results = []
        for market, exchange in _MARKETS:
            session = validate_session_timestamp(symbol=market, exchange=exchange, market_timestamp=now, evaluated_at=now, validation_mode="LENIENT_ANALYSIS")
            entry_allowed = bool(
                getattr(session, "paper_execution_allowed", False)
            )
            try:
                evidence = self.child_authority(market, exchange, entry_allowed)
            except Exception as exc:
                # Unexpected authority failures stay distinct from certified
                # provider incidents.  Keep only the exception class: no
                # stack trace, raw payload, credential, or message is stored.
                reason = "".join(
                    character if character.isalnum() else "_"
                    for character in type(exc).__name__.upper()
                )
                results.append((
                    market,
                    "INTERNAL_CHILD_FAILURE",
                    Task9InternalChildFailureV1(
                        reason_code=f"INTERNAL_CHILD_FAILURE_{reason}",
                    ),
                ))
                continue
            if evidence.prediction.underlying_symbol != market or evidence.prediction.exchange != exchange:
                raise ValueError("child evidence identity mismatch")
            if evidence.evidence_status == "DATA_INCIDENT":
                decision = evaluate_task9_live_paper_trade_counting(Task9LivePaperTradeCountingInputV1(prediction=evidence.prediction, lifecycle_outcome=None, reconciliation=None, record_source=evidence.record_source, session_status="REAL_TIME_MARKET_SESSION", evidence_status="DATA_INCIDENT", official_run_id=self.official_run_id, record_run_id=self.official_run_id, official_start_at=self.official_start_at, evaluated_at=now, run_classification=self.run_classification))
                results.append((market, "DATA_INCIDENT", decision))
                continue
            # Counting is intentionally impossible until an entered position has
            # reached terminal state and reconciliation has completed.
            decision = None
            if evidence.terminal_position_closed and evidence.lifecycle_outcome is not None and evidence.reconciliation is not None:
                decision = evaluate_task9_live_paper_trade_counting(Task9LivePaperTradeCountingInputV1(prediction=evidence.prediction, lifecycle_outcome=evidence.lifecycle_outcome, reconciliation=evidence.reconciliation, record_source=evidence.record_source, session_status="REAL_TIME_MARKET_SESSION", evidence_status=evidence.evidence_status, official_run_id=self.official_run_id, record_run_id=self.official_run_id, official_start_at=self.official_start_at, evaluated_at=now, run_classification=self.run_classification))
            results.append((market, "ENTRY_ALLOWED" if entry_allowed else "MONITOR_ONLY", decision))
        result = Task9LivePaperCycleResultV1(cycle_id=cycle_id, started_at=now, completed_at=now, market_results=tuple(results))
        self.persist(result)
        if self.publish is not None:
            self.publish(result)
        return result
