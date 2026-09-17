"""Restart-safe due prediction outcome batch evaluation."""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from services.contracts.prediction_outcome_evaluation_input_v1 import PredictionOutcomeEvaluationInputV1
from services.contracts.prediction_outcome_record_v1 import PredictionOutcomeRecordV1
from services.contracts.prediction_record_v1 import prediction_record_from_dict
from services.paper_orchestration.prediction_ledger import PredictionLedger
from services.paper_orchestration.prediction_outcome_evaluator import build_unevaluable_prediction_outcome, evaluate_prediction_outcome
from services.paper_orchestration.prediction_outcome_ledger import PredictionOutcomeLedger

PriceReader = Callable[[str, str], Mapping[str, Any]]
Clock = Callable[[], datetime]

def _aware(value, name):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(name)
    return value

def _positive(value, name):
    if type(value) not in (int, float) or isinstance(value, bool) or not math.isfinite(value) or value <= 0.0:
        raise ValueError(name)
    return float(value)

@dataclass(frozen=True, slots=True)
class PredictionOutcomeBatchResultV1:
    evaluated_records: tuple[PredictionOutcomeRecordV1, ...]
    pending_prediction_ids: tuple[str, ...]
    skipped_existing_prediction_ids: tuple[str, ...]
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self):
        if any(type(item) is not PredictionOutcomeRecordV1 for item in self.evaluated_records):
            raise TypeError("evaluated_records")
        for name in ("pending_prediction_ids", "skipped_existing_prediction_ids"):
            value = getattr(self, name)
            if type(value) is not tuple or any(type(item) is not str or not item.strip() for item in value):
                raise TypeError(name)
        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False or self.broker_order_submission is not False:
            raise ValueError("PAPER-only batch result")

class PendingPredictionOutcomeEvaluator:
    def __init__(self, *, prediction_ledger, outcome_ledger, price_reader, clock, evaluation_horizon_seconds=900.0, threshold_percent=0.20):
        if type(prediction_ledger) is not PredictionLedger:
            raise TypeError("prediction_ledger")
        if type(outcome_ledger) is not PredictionOutcomeLedger:
            raise TypeError("outcome_ledger")
        if not callable(price_reader):
            raise TypeError("price_reader")
        if not callable(clock):
            raise TypeError("clock")
        self.prediction_ledger = prediction_ledger
        self.outcome_ledger = outcome_ledger
        self.price_reader = price_reader
        self.clock = clock
        self.evaluation_horizon_seconds = _positive(evaluation_horizon_seconds, "evaluation_horizon_seconds")
        if type(threshold_percent) not in (int, float) or isinstance(threshold_percent, bool) or not math.isfinite(threshold_percent) or threshold_percent < 0.0:
            raise ValueError("threshold_percent")
        self.threshold_percent = float(threshold_percent)

    def __call__(self):
        now = _aware(self.clock(), "clock result")
        evaluated, pending, skipped = [], [], []
        for raw in self.prediction_ledger.all_records():
            prediction = prediction_record_from_dict(raw)
            if self.outcome_ledger.has_outcome_for_prediction(prediction.prediction_id):
                skipped.append(prediction.prediction_id)
                continue
            due = prediction.completed_at + timedelta(seconds=self.evaluation_horizon_seconds)
            if now < due:
                pending.append(prediction.prediction_id)
                continue
            try:
                observed = self.price_reader(prediction.underlying_symbol, prediction.exchange)
                if not isinstance(observed, Mapping):
                    raise TypeError("price_reader must return a mapping")
                end_price = _positive(observed.get("spot_price", observed.get("ltp", observed.get("last_price"))), "end_underlying_price")
                observation_id = observed.get("observation_id")
                if type(observation_id) is not str or not observation_id.strip():
                    raise ValueError("evaluation observation_id")
                observed_at = _aware(observed.get("observed_at", observed.get("market_timestamp")), "evaluation observed_at")
                if observed_at < due:
                    raise ValueError("evaluation evidence precedes due boundary")
                record = evaluate_prediction_outcome(PredictionOutcomeEvaluationInputV1(
                    prediction=prediction,
                    evaluation_observation_id=observation_id.strip(),
                    start_underlying_price=prediction.start_underlying_price,
                    end_underlying_price=end_price,
                    evaluation_due_at=due,
                    evaluated_at=max(now, observed_at),
                    evaluation_horizon_seconds=self.evaluation_horizon_seconds,
                    threshold_percent=self.threshold_percent,
                ))
            except Exception:
                record = build_unevaluable_prediction_outcome(
                    prediction=prediction, evaluation_due_at=due, evaluated_at=now,
                    evaluation_horizon_seconds=self.evaluation_horizon_seconds,
                    threshold_percent=self.threshold_percent,
                    blocker="EVALUATION_PRICE_OR_TIMESTAMP_UNAVAILABLE",
                )
            self.outcome_ledger.save(record)
            evaluated.append(record)
        return PredictionOutcomeBatchResultV1(tuple(evaluated), tuple(pending), tuple(skipped))
