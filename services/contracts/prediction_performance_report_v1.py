"""Immutable read-only report contracts for prediction performance."""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import ClassVar


_ACTIONS = {"CALL", "PUT", "WAIT"}
_OUTCOMES = {
    "CORRECT",
    "INCORRECT",
    "FLAT",
    "GOOD_WAIT",
    "MISSED_OPPORTUNITY",
    "NEUTRAL_WAIT",
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


def _count(value: object, name: str) -> int:
    if (
        type(value) is not int
        or isinstance(value, bool)
        or value < 0
    ):
        raise ValueError(name)
    return value


def _percent(
    value: object,
    name: str,
) -> float | None:
    if value is None:
        return None
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not math.isfinite(value)
        or not 0.0 <= value <= 100.0
    ):
        raise ValueError(name)
    return float(value)


def _distribution(
    value: object,
    *,
    vocabulary: set[str],
    name: str,
) -> tuple[tuple[str, int], ...]:
    if type(value) is not tuple:
        raise TypeError(name)

    normalized: list[tuple[str, int]] = []
    seen: set[str] = set()

    for item in value:
        if (
            type(item) is not tuple
            or len(item) != 2
        ):
            raise TypeError(name)
        key = _text(item[0], name).upper()
        count = _count(item[1], name)
        if key not in vocabulary:
            raise ValueError(name)
        if key in seen:
            raise ValueError(f"duplicate {name} key")
        seen.add(key)
        normalized.append((key, count))

    return tuple(sorted(normalized))


@dataclass(frozen=True, slots=True)
class PredictionPerformanceMetricsV1:
    """One immutable aggregate metrics block."""

    prediction_count: int
    evaluated_count: int
    pending_count: int
    unevaluable_count: int
    directional_resolved_count: int
    directional_correct_count: int
    directional_incorrect_count: int
    directional_flat_count: int
    abstention_resolved_count: int
    good_wait_count: int
    missed_opportunity_count: int
    neutral_wait_count: int
    directional_accuracy_percent: float | None
    wait_quality_percent: float | None
    action_distribution: tuple[tuple[str, int], ...]
    outcome_distribution: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        for name in (
            "prediction_count",
            "evaluated_count",
            "pending_count",
            "unevaluable_count",
            "directional_resolved_count",
            "directional_correct_count",
            "directional_incorrect_count",
            "directional_flat_count",
            "abstention_resolved_count",
            "good_wait_count",
            "missed_opportunity_count",
            "neutral_wait_count",
        ):
            object.__setattr__(
                self,
                name,
                _count(getattr(self, name), name),
            )

        if (
            self.evaluated_count
            + self.pending_count
            != self.prediction_count
        ):
            raise ValueError(
                "prediction count reconciliation"
            )

        if (
            self.directional_correct_count
            + self.directional_incorrect_count
            != self.directional_resolved_count
        ):
            raise ValueError(
                "directional count reconciliation"
            )

        if (
            self.good_wait_count
            + self.missed_opportunity_count
            + self.neutral_wait_count
            != self.abstention_resolved_count
        ):
            raise ValueError(
                "abstention count reconciliation"
            )

        directional_accuracy = _percent(
            self.directional_accuracy_percent,
            "directional_accuracy_percent",
        )
        wait_quality = _percent(
            self.wait_quality_percent,
            "wait_quality_percent",
        )

        expected_directional = (
            self.directional_correct_count
            / self.directional_resolved_count
            * 100.0
            if self.directional_resolved_count
            else None
        )
        if (
            expected_directional is None
            and directional_accuracy is not None
        ) or (
            expected_directional is not None
            and (
                directional_accuracy is None
                or not math.isclose(
                    directional_accuracy,
                    expected_directional,
                    rel_tol=0.0,
                    abs_tol=1e-9,
                )
            )
        ):
            raise ValueError(
                "directional accuracy mismatch"
            )

        wait_denominator = (
            self.good_wait_count
            + self.missed_opportunity_count
        )
        expected_wait = (
            self.good_wait_count
            / wait_denominator
            * 100.0
            if wait_denominator
            else None
        )
        if (
            expected_wait is None
            and wait_quality is not None
        ) or (
            expected_wait is not None
            and (
                wait_quality is None
                or not math.isclose(
                    wait_quality,
                    expected_wait,
                    rel_tol=0.0,
                    abs_tol=1e-9,
                )
            )
        ):
            raise ValueError(
                "wait quality mismatch"
            )

        actions = _distribution(
            self.action_distribution,
            vocabulary=_ACTIONS,
            name="action_distribution",
        )
        outcomes = _distribution(
            self.outcome_distribution,
            vocabulary=_OUTCOMES,
            name="outcome_distribution",
        )

        if sum(count for _, count in actions) != self.prediction_count:
            raise ValueError(
                "action distribution reconciliation"
            )
        if sum(count for _, count in outcomes) != self.evaluated_count:
            raise ValueError(
                "outcome distribution reconciliation"
            )

        object.__setattr__(
            self,
            "directional_accuracy_percent",
            directional_accuracy,
        )
        object.__setattr__(
            self,
            "wait_quality_percent",
            wait_quality,
        )
        object.__setattr__(
            self,
            "action_distribution",
            actions,
        )
        object.__setattr__(
            self,
            "outcome_distribution",
            outcomes,
        )

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["action_distribution"] = {
            key: count
            for key, count in self.action_distribution
        }
        result["outcome_distribution"] = {
            key: count
            for key, count in self.outcome_distribution
        }
        return result


@dataclass(frozen=True, slots=True)
class PredictionPerformanceReportV1:
    """Deterministic PAPER-only report covering NIFTY and SENSEX."""

    SCHEMA_VERSION: ClassVar[str] = (
        "prediction_performance_report.v1"
    )

    report_id: str
    generated_at: datetime
    period_started_at: datetime | None
    period_ended_at: datetime | None
    overall: PredictionPerformanceMetricsV1
    nifty: PredictionPerformanceMetricsV1
    sensex: PredictionPerformanceMetricsV1
    source_prediction_count: int
    source_outcome_count: int
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    read_only: bool = True
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "report_id",
            _text(self.report_id, "report_id"),
        )
        object.__setattr__(
            self,
            "generated_at",
            _aware(self.generated_at, "generated_at"),
        )

        for name in (
            "period_started_at",
            "period_ended_at",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    _aware(value, name),
                )

        if (
            self.period_started_at is None
            and self.period_ended_at is not None
        ) or (
            self.period_started_at is not None
            and self.period_ended_at is None
        ):
            raise ValueError(
                "report period must be fully present or absent"
            )
        if (
            self.period_started_at is not None
            and self.period_ended_at is not None
            and self.period_started_at > self.period_ended_at
        ):
            raise ValueError("report period ordering")

        for name in (
            "overall",
            "nifty",
            "sensex",
        ):
            if (
                type(getattr(self, name))
                is not PredictionPerformanceMetricsV1
            ):
                raise TypeError(name)

        object.__setattr__(
            self,
            "source_prediction_count",
            _count(
                self.source_prediction_count,
                "source_prediction_count",
            ),
        )
        object.__setattr__(
            self,
            "source_outcome_count",
            _count(
                self.source_outcome_count,
                "source_outcome_count",
            ),
        )

        if (
            self.overall.prediction_count
            != self.source_prediction_count
        ):
            raise ValueError(
                "source prediction count mismatch"
            )
        if (
            self.overall.evaluated_count
            != self.source_outcome_count
        ):
            raise ValueError(
                "source outcome count mismatch"
            )
        if (
            self.nifty.prediction_count
            + self.sensex.prediction_count
            != self.overall.prediction_count
        ):
            raise ValueError(
                "market prediction reconciliation"
            )
        if (
            self.nifty.evaluated_count
            + self.sensex.evaluated_count
            != self.overall.evaluated_count
        ):
            raise ValueError(
                "market outcome reconciliation"
            )

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
            or self.read_only is not True
            or self.schema_version != self.SCHEMA_VERSION
        ):
            raise ValueError(
                "PAPER-only read-only prediction report"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at.isoformat(),
            "period_started_at": (
                self.period_started_at.isoformat()
                if self.period_started_at is not None
                else None
            ),
            "period_ended_at": (
                self.period_ended_at.isoformat()
                if self.period_ended_at is not None
                else None
            ),
            "overall": self.overall.to_dict(),
            "nifty": self.nifty.to_dict(),
            "sensex": self.sensex.to_dict(),
            "source_prediction_count": (
                self.source_prediction_count
            ),
            "source_outcome_count": (
                self.source_outcome_count
            ),
            "execution_mode": self.execution_mode,
            "live_execution_eligible": (
                self.live_execution_eligible
            ),
            "broker_order_submission": (
                self.broker_order_submission
            ),
            "read_only": self.read_only,
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
