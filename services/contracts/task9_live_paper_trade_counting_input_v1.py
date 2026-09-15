"""Immutable Task 9 live PAPER trade-counting input."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from services.contracts.prediction_lifecycle_outcome_record_v1 import (
    PredictionLifecycleOutcomeRecordV1,
)
from services.contracts.prediction_lifecycle_reconciliation_result_v1 import (
    PredictionLifecycleReconciliationResultV1,
)
from services.contracts.prediction_record_v1 import (
    PredictionRecordV1,
)
from services.contracts.task9_run_classification_v1 import validate_task9_run_classification


_SOURCE_KINDS = {
    "LIVE_REAL_TIME",
    "REPLAY",
    "BACKTEST",
    "DIAGNOSTIC",
    "FIXTURE",
    "DEVELOPMENT",
}

_SESSION_STATUSES = {
    "REAL_TIME_MARKET_SESSION",
    "OUT_OF_SESSION",
    "UNKNOWN",
}

_EVIDENCE_STATUSES = {
    "VALID",
    "INVALID",
    "DATA_INCIDENT",
}


def _text(value: object, name: str) -> str:
    if type(value) is not str:
        raise TypeError(name)
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(name)
    return cleaned


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


@dataclass(frozen=True, slots=True)
class Task9LivePaperTradeCountingInputV1:
    """Evidence required for one Task 9 executed-trade count decision."""

    SCHEMA_VERSION: ClassVar[str] = (
        "task9_live_paper_trade_counting_input.v1"
    )

    prediction: PredictionRecordV1
    lifecycle_outcome: PredictionLifecycleOutcomeRecordV1 | None
    reconciliation: PredictionLifecycleReconciliationResultV1 | None

    record_source: str
    session_status: str
    evidence_status: str

    official_run_id: str
    record_run_id: str
    official_start_at: datetime
    evaluated_at: datetime
    run_classification: str = "OFFICIAL_CERTIFICATION"

    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.prediction) is not PredictionRecordV1:
            raise TypeError("prediction")

        if (
            self.lifecycle_outcome is not None
            and type(self.lifecycle_outcome)
            is not PredictionLifecycleOutcomeRecordV1
        ):
            raise TypeError("lifecycle_outcome")

        if (
            self.reconciliation is not None
            and type(self.reconciliation)
            is not PredictionLifecycleReconciliationResultV1
        ):
            raise TypeError("reconciliation")

        source = _text(
            self.record_source,
            "record_source",
        ).upper()
        session = _text(
            self.session_status,
            "session_status",
        ).upper()
        evidence = _text(
            self.evidence_status,
            "evidence_status",
        ).upper()

        if source not in _SOURCE_KINDS:
            raise ValueError("record_source")
        if session not in _SESSION_STATUSES:
            raise ValueError("session_status")
        if evidence not in _EVIDENCE_STATUSES:
            raise ValueError("evidence_status")

        object.__setattr__(self, "record_source", source)
        object.__setattr__(self, "session_status", session)
        object.__setattr__(self, "evidence_status", evidence)

        for name in (
            "official_run_id",
            "record_run_id",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )

        object.__setattr__(
            self,
            "official_start_at",
            _aware(self.official_start_at, "official_start_at"),
        )
        object.__setattr__(
            self,
            "evaluated_at",
            _aware(self.evaluated_at, "evaluated_at"),
        )
        object.__setattr__(self, "run_classification", validate_task9_run_classification(self.run_classification))

        if self.evaluated_at < self.prediction.completed_at:
            raise ValueError(
                "evaluated_at cannot precede prediction completion"
            )

        if self.lifecycle_outcome is not None:
            outcome = self.lifecycle_outcome
            if (
                outcome.prediction_id
                != self.prediction.prediction_id
                or outcome.parent_cycle_id
                != self.prediction.parent_cycle_id
                or outcome.underlying_symbol
                != self.prediction.underlying_symbol
                or outcome.exchange
                != self.prediction.exchange
                or outcome.predicted_action
                != self.prediction.predicted_action
            ):
                raise ValueError(
                    "prediction/lifecycle outcome identity mismatch"
                )

        if self.reconciliation is not None:
            reconciliation = self.reconciliation
            if (
                reconciliation.prediction_id
                != self.prediction.prediction_id
                or reconciliation.underlying_symbol
                != self.prediction.underlying_symbol
                or reconciliation.exchange
                != self.prediction.exchange
                or reconciliation.predicted_action
                != self.prediction.predicted_action
            ):
                raise ValueError(
                    "prediction/reconciliation identity mismatch"
                )

            if (
                self.lifecycle_outcome is not None
                and reconciliation.lifecycle_outcome_id
                != self.lifecycle_outcome.outcome_id
            ):
                raise ValueError(
                    "lifecycle outcome/reconciliation identity mismatch"
                )

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
            or self.schema_version != self.SCHEMA_VERSION
        ):
            raise ValueError(
                "Task 9 counting input must remain PAPER-only"
            )
