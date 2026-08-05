"""Supplied-evidence input for deterministic prediction outcome evaluation."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from services.contracts.prediction_record_v1 import (
    PredictionRecordV1,
)


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


def _positive_number(
    value: object,
    name: str,
) -> float:
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value <= 0.0
    ):
        raise ValueError(name)
    return float(value)


def _nonnegative_number(
    value: object,
    name: str,
) -> float:
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value < 0.0
    ):
        raise ValueError(name)
    return float(value)


@dataclass(frozen=True, slots=True)
class PredictionOutcomeEvaluationInputV1:
    """One supplied underlying-price observation for one prediction."""

    SCHEMA_VERSION: ClassVar[str] = (
        "prediction_outcome_evaluation_input.v1"
    )

    prediction: PredictionRecordV1
    evaluation_observation_id: str
    start_underlying_price: float
    end_underlying_price: float
    evaluation_due_at: datetime
    evaluated_at: datetime
    evaluation_horizon_seconds: float
    threshold_percent: float
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.prediction) is not PredictionRecordV1:
            raise TypeError("prediction")

        object.__setattr__(
            self,
            "evaluation_observation_id",
            _text(
                self.evaluation_observation_id,
                "evaluation_observation_id",
            ),
        )
        object.__setattr__(
            self,
            "start_underlying_price",
            _positive_number(
                self.start_underlying_price,
                "start_underlying_price",
            ),
        )
        object.__setattr__(
            self,
            "end_underlying_price",
            _positive_number(
                self.end_underlying_price,
                "end_underlying_price",
            ),
        )

        due = _aware(
            self.evaluation_due_at,
            "evaluation_due_at",
        )
        evaluated = _aware(
            self.evaluated_at,
            "evaluated_at",
        )

        if (
            due
            < self.prediction.completed_at
        ):
            raise ValueError(
                "evaluation_due_at cannot precede prediction completion"
            )
        if evaluated < due:
            raise ValueError(
                "evaluated_at cannot precede evaluation_due_at"
            )

        horizon = _nonnegative_number(
            self.evaluation_horizon_seconds,
            "evaluation_horizon_seconds",
        )
        if horizon <= 0.0:
            raise ValueError(
                "evaluation_horizon_seconds must be positive"
            )

        actual_horizon = (
            due
            - self.prediction.completed_at
        ).total_seconds()
        if not math.isclose(
            horizon,
            actual_horizon,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError(
                "evaluation_horizon_seconds mismatch"
            )

        object.__setattr__(
            self,
            "evaluation_horizon_seconds",
            horizon,
        )
        object.__setattr__(
            self,
            "threshold_percent",
            _nonnegative_number(
                self.threshold_percent,
                "threshold_percent",
            ),
        )

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
            or self.schema_version != self.SCHEMA_VERSION
        ):
            raise ValueError(
                "PAPER-only prediction outcome input"
            )
