"""Immutable PAPER-only outcome record for one prediction."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import ClassVar


_IDENTITIES = {
    ("NIFTY", "NSE"),
    ("SENSEX", "BSE"),
}
_ACTIONS = {
    "CALL",
    "PUT",
    "WAIT",
}
_EVALUATION_KINDS = {
    "DIRECTIONAL",
    "ABSTENTION",
}
_OUTCOMES = {
    "CORRECT",
    "INCORRECT",
    "FLAT",
    "GOOD_WAIT",
    "MISSED_OPPORTUNITY",
    "NEUTRAL_WAIT",
    "UNEVALUABLE",
}
_STATUSES = {
    "EVALUATED",
    "UNEVALUABLE",
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


def _optional_price(
    value: object,
    name: str,
) -> float | None:
    if value is None:
        return None
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value <= 0.0
    ):
        raise ValueError(name)
    return float(value)


def _optional_number(
    value: object,
    name: str,
) -> float | None:
    if value is None:
        return None
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not math.isfinite(value)
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


def _messages(
    value: object,
    name: str,
) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise TypeError(name)
    return tuple(
        dict.fromkeys(
            _text(item, name)
            for item in value
        )
    )


@dataclass(frozen=True, slots=True)
class PredictionOutcomeRecordV1:
    """One immutable evaluated outcome for a retained prediction."""

    SCHEMA_VERSION: ClassVar[str] = (
        "prediction_outcome_record.v1"
    )

    outcome_id: str
    prediction_id: str
    parent_cycle_id: str
    decision_result_id: str
    underlying_symbol: str
    exchange: str
    predicted_action: str
    evaluation_kind: str
    prediction_completed_at: datetime
    evaluation_due_at: datetime
    evaluated_at: datetime
    evaluation_status: str
    outcome: str
    start_underlying_price: float | None
    end_underlying_price: float | None
    movement_points: float | None
    movement_percent: float | None
    absolute_movement_percent: float | None
    evaluation_horizon_seconds: float
    threshold_percent: float
    evidence_observation_id: str | None = None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "outcome_id",
            "prediction_id",
            "parent_cycle_id",
            "decision_result_id",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )

        identity = (
            _text(
                self.underlying_symbol,
                "underlying_symbol",
            ).upper(),
            _text(
                self.exchange,
                "exchange",
            ).upper(),
        )
        if identity not in _IDENTITIES:
            raise ValueError("market identity")
        object.__setattr__(
            self,
            "underlying_symbol",
            identity[0],
        )
        object.__setattr__(
            self,
            "exchange",
            identity[1],
        )

        action = _text(
            self.predicted_action,
            "predicted_action",
        ).upper()
        kind = _text(
            self.evaluation_kind,
            "evaluation_kind",
        ).upper()
        status = _text(
            self.evaluation_status,
            "evaluation_status",
        ).upper()
        outcome = _text(
            self.outcome,
            "outcome",
        ).upper()

        if action not in _ACTIONS:
            raise ValueError("predicted_action")
        if kind not in _EVALUATION_KINDS:
            raise ValueError("evaluation_kind")
        if status not in _STATUSES:
            raise ValueError("evaluation_status")
        if outcome not in _OUTCOMES:
            raise ValueError("outcome")

        if (
            action in {"CALL", "PUT"}
            and kind != "DIRECTIONAL"
        ):
            raise ValueError(
                "CALL/PUT requires DIRECTIONAL evaluation"
            )
        if (
            action == "WAIT"
            and kind != "ABSTENTION"
        ):
            raise ValueError(
                "WAIT requires ABSTENTION evaluation"
            )

        object.__setattr__(
            self,
            "predicted_action",
            action,
        )
        object.__setattr__(
            self,
            "evaluation_kind",
            kind,
        )
        object.__setattr__(
            self,
            "evaluation_status",
            status,
        )
        object.__setattr__(
            self,
            "outcome",
            outcome,
        )

        prediction_completed = _aware(
            self.prediction_completed_at,
            "prediction_completed_at",
        )
        due = _aware(
            self.evaluation_due_at,
            "evaluation_due_at",
        )
        evaluated = _aware(
            self.evaluated_at,
            "evaluated_at",
        )
        if prediction_completed > due:
            raise ValueError(
                "prediction_completed_at must not exceed evaluation_due_at"
            )
        if due > evaluated:
            raise ValueError(
                "evaluation_due_at must not exceed evaluated_at"
            )

        object.__setattr__(
            self,
            "start_underlying_price",
            _optional_price(
                self.start_underlying_price,
                "start_underlying_price",
            ),
        )
        object.__setattr__(
            self,
            "end_underlying_price",
            _optional_price(
                self.end_underlying_price,
                "end_underlying_price",
            ),
        )
        for name in (
            "movement_points",
            "movement_percent",
            "absolute_movement_percent",
        ):
            object.__setattr__(
                self,
                name,
                _optional_number(
                    getattr(self, name),
                    name,
                ),
            )

        horizon = _nonnegative_number(
            self.evaluation_horizon_seconds,
            "evaluation_horizon_seconds",
        )
        threshold = _nonnegative_number(
            self.threshold_percent,
            "threshold_percent",
        )
        if horizon <= 0.0:
            raise ValueError(
                "evaluation_horizon_seconds must be positive"
            )
        object.__setattr__(
            self,
            "evaluation_horizon_seconds",
            horizon,
        )
        object.__setattr__(
            self,
            "threshold_percent",
            threshold,
        )

        if self.evidence_observation_id is not None:
            object.__setattr__(
                self,
                "evidence_observation_id",
                _text(
                    self.evidence_observation_id,
                    "evidence_observation_id",
                ),
            )

        object.__setattr__(
            self,
            "blockers",
            _messages(self.blockers, "blockers"),
        )
        object.__setattr__(
            self,
            "warnings",
            _messages(self.warnings, "warnings"),
        )

        prices = (
            self.start_underlying_price,
            self.end_underlying_price,
        )
        movements = (
            self.movement_points,
            self.movement_percent,
            self.absolute_movement_percent,
        )

        if status == "EVALUATED":
            if any(value is None for value in prices):
                raise ValueError(
                    "evaluated outcome requires both prices"
                )
            if any(value is None for value in movements):
                raise ValueError(
                    "evaluated outcome requires movement values"
                )
            if outcome == "UNEVALUABLE":
                raise ValueError(
                    "evaluated outcome cannot be UNEVALUABLE"
                )
            if self.blockers:
                raise ValueError(
                    "evaluated outcome cannot contain blockers"
                )
            if self.evidence_observation_id is None:
                raise ValueError(
                    "evaluated outcome requires evidence observation"
                )

            expected_points = (
                self.end_underlying_price
                - self.start_underlying_price
            )
            expected_percent = (
                expected_points
                / self.start_underlying_price
                * 100.0
            )
            if not math.isclose(
                self.movement_points,
                expected_points,
                rel_tol=0.0,
                abs_tol=1e-9,
            ):
                raise ValueError(
                    "movement_points mismatch"
                )
            if not math.isclose(
                self.movement_percent,
                expected_percent,
                rel_tol=0.0,
                abs_tol=1e-9,
            ):
                raise ValueError(
                    "movement_percent mismatch"
                )
            if not math.isclose(
                self.absolute_movement_percent,
                abs(expected_percent),
                rel_tol=0.0,
                abs_tol=1e-9,
            ):
                raise ValueError(
                    "absolute_movement_percent mismatch"
                )
        else:
            if outcome != "UNEVALUABLE":
                raise ValueError(
                    "UNEVALUABLE status requires UNEVALUABLE outcome"
                )
            if not self.blockers:
                raise ValueError(
                    "unevaluable outcome requires blocker"
                )
            if any(value is not None for value in prices):
                raise ValueError(
                    "unevaluable outcome cannot contain prices"
                )
            if any(value is not None for value in movements):
                raise ValueError(
                    "unevaluable outcome cannot contain movements"
                )
            if self.evidence_observation_id is not None:
                raise ValueError(
                    "unevaluable outcome cannot contain observation"
                )

        if kind == "DIRECTIONAL" and outcome not in {
            "CORRECT",
            "INCORRECT",
            "FLAT",
            "UNEVALUABLE",
        }:
            raise ValueError(
                "directional outcome vocabulary"
            )
        if kind == "ABSTENTION" and outcome not in {
            "GOOD_WAIT",
            "MISSED_OPPORTUNITY",
            "NEUTRAL_WAIT",
            "UNEVALUABLE",
        }:
            raise ValueError(
                "abstention outcome vocabulary"
            )

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
            or self.schema_version != self.SCHEMA_VERSION
        ):
            raise ValueError(
                "PAPER-only prediction outcome record"
            )

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        for name in (
            "prediction_completed_at",
            "evaluation_due_at",
            "evaluated_at",
        ):
            result[name] = getattr(
                self,
                name,
            ).isoformat()
        result["blockers"] = list(
            self.blockers
        )
        result["warnings"] = list(
            self.warnings
        )
        return result

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @property
    def semantic_hash(self) -> str:
        return hashlib.sha256(
            self.to_json().encode("utf-8")
        ).hexdigest()
