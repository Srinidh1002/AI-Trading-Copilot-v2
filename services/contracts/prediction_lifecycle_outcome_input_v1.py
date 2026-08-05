"""Immutable input for one prediction lifecycle outcome evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from services.contracts.prediction_lifecycle_outcome_policy_v1 import (
    PredictionLifecycleOutcomePolicyV1,
)
from services.contracts.prediction_observation_window_v1 import (
    PredictionObservationWindowV1,
)
from services.contracts.prediction_record_v1 import PredictionRecordV1


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


@dataclass(frozen=True, slots=True)
class PredictionLifecycleOutcomeInputV1:
    """Supplied ordered evidence, policy and evaluation boundary."""

    SCHEMA_VERSION: ClassVar[str] = (
        "prediction_lifecycle_outcome_input.v1"
    )

    prediction: PredictionRecordV1
    observation_window: PredictionObservationWindowV1
    policy: PredictionLifecycleOutcomePolicyV1
    evaluated_at: datetime
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.prediction) is not PredictionRecordV1:
            raise TypeError("prediction")
        if type(self.observation_window) is not PredictionObservationWindowV1:
            raise TypeError("observation_window")
        if type(self.policy) is not PredictionLifecycleOutcomePolicyV1:
            raise TypeError("policy")

        evaluated = _aware(self.evaluated_at, "evaluated_at")
        if evaluated < self.prediction.completed_at:
            raise ValueError("evaluated_at precedes prediction completion")
        if (
            self.observation_window.observations
            and evaluated < self.observation_window.observations[-1].observed_at
        ):
            raise ValueError("evaluated_at precedes supplied observation")
        object.__setattr__(self, "evaluated_at", evaluated)

        window = self.observation_window
        if (
            window.prediction_id != self.prediction.prediction_id
            or window.parent_cycle_id != self.prediction.parent_cycle_id
            or window.underlying_symbol != self.prediction.underlying_symbol
            or window.exchange != self.prediction.exchange
            or window.window_started_at != self.prediction.completed_at
        ):
            raise ValueError("prediction/window identity mismatch")

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
            or self.schema_version != self.SCHEMA_VERSION
        ):
            raise ValueError("PAPER-only lifecycle outcome input")
