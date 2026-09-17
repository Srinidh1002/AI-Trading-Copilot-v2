"""Canonical option-chain intelligence policy contract.

The values in this policy are initial deterministic architectural thresholds.
They are not statistically calibrated trading thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite
from typing import Any, ClassVar


_ALLOWED_BEHAVIORS = frozenset(
    {
        "BLOCK",
        "WARN",
        "ALLOW",
    }
)

_REQUIRED_METRICS = (
    "PCR_OPEN_INTEREST",
    "PCR_VOLUME",
    "OI_CONCENTRATION",
    "OI_BUILDUP",
    "MAX_PAIN",
    "IV_SKEW",
    "SUPPORT_RESISTANCE",
)


def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")

    return normalized


def _require_positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")

    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero")

    return value


def _require_non_negative_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")

    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")

    return value


def _require_finite_float(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a finite number")

    normalized = float(value)

    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite")

    return normalized


def _require_positive_float(value: Any, field_name: str) -> float:
    normalized = _require_finite_float(value, field_name)

    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be greater than zero")

    return normalized


def _require_non_negative_float(value: Any, field_name: str) -> float:
    normalized = _require_finite_float(value, field_name)

    if normalized < 0.0:
        raise ValueError(f"{field_name} must be non-negative")

    return normalized


def _require_unit_interval(value: Any, field_name: str) -> float:
    normalized = _require_finite_float(value, field_name)

    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0")

    return normalized


def _require_behavior(value: Any, field_name: str) -> str:
    normalized = _require_non_empty_string(
        value,
        field_name,
    ).upper()

    if normalized not in _ALLOWED_BEHAVIORS:
        raise ValueError(
            f"{field_name} must be one of "
            f"{tuple(sorted(_ALLOWED_BEHAVIORS))}"
        )

    return normalized


def _require_metric_weights(
    value: Any,
) -> tuple[tuple[str, float], ...]:
    if not isinstance(value, tuple):
        raise TypeError("metric_weights must be a tuple")

    if len(value) != len(_REQUIRED_METRICS):
        raise ValueError(
            "metric_weights must contain every required metric exactly once"
        )

    normalized: list[tuple[str, float]] = []
    seen: set[str] = set()

    for item in value:
        if not isinstance(item, tuple) or len(item) != 2:
            raise TypeError(
                "each metric_weights item must be a two-item tuple"
            )

        raw_name, raw_weight = item

        name = _require_non_empty_string(
            raw_name,
            "metric weight name",
        ).upper()

        if name not in _REQUIRED_METRICS:
            raise ValueError(
                f"unsupported metric weight name: {name}"
            )

        if name in seen:
            raise ValueError(
                "metric_weights must not contain duplicate metric names"
            )

        weight = _require_unit_interval(
            raw_weight,
            f"metric weight {name}",
        )

        seen.add(name)
        normalized.append((name, weight))

    if tuple(name for name, _ in normalized) != _REQUIRED_METRICS:
        raise ValueError(
            "metric_weights must follow canonical metric order"
        )

    total_weight = sum(weight for _, weight in normalized)

    if not isclose(
        total_weight,
        1.0,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError("metric_weights must sum to exactly 1.0")

    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class OptionChainIntelligencePolicyV1:
    """Deterministic policy for canonical option-chain intelligence."""

    SCHEMA_VERSION: ClassVar[str] = (
        "option_chain_intelligence_policy.v1"
    )
    EXECUTION_MODE: ClassVar[str] = "PAPER"
    LIVE_EXECUTION_ELIGIBLE: ClassVar[bool] = False

    policy_name: str

    metric_weights: tuple[tuple[str, float], ...]

    pcr_bullish_threshold: float
    pcr_bearish_threshold: float
    pcr_extreme_high_threshold: float
    pcr_extreme_low_threshold: float

    oi_concentration_high_ratio: float
    oi_concentration_low_ratio: float
    oi_buildup_minimum_absolute_change: int

    max_pain_near_distance_bps: float
    max_pain_far_distance_bps: float

    iv_skew_material_difference: float
    support_resistance_top_n: int
    minimum_valid_metrics: int

    bullish_score_threshold: float
    bearish_score_threshold: float
    conflicting_score_tolerance: float

    insufficient_metrics_behavior: str
    missing_metric_behavior: str
    conflicting_signal_behavior: str

    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        policy_name = _require_non_empty_string(
            self.policy_name,
            "policy_name",
        )
        object.__setattr__(self, "policy_name", policy_name)

        metric_weights = _require_metric_weights(
            self.metric_weights,
        )
        object.__setattr__(
            self,
            "metric_weights",
            metric_weights,
        )

        pcr_bullish_threshold = _require_positive_float(
            self.pcr_bullish_threshold,
            "pcr_bullish_threshold",
        )
        pcr_bearish_threshold = _require_positive_float(
            self.pcr_bearish_threshold,
            "pcr_bearish_threshold",
        )
        pcr_extreme_high_threshold = _require_positive_float(
            self.pcr_extreme_high_threshold,
            "pcr_extreme_high_threshold",
        )
        pcr_extreme_low_threshold = _require_positive_float(
            self.pcr_extreme_low_threshold,
            "pcr_extreme_low_threshold",
        )

        if not (
            pcr_extreme_low_threshold
            < pcr_bearish_threshold
            < pcr_bullish_threshold
            < pcr_extreme_high_threshold
        ):
            raise ValueError(
                "PCR thresholds must satisfy: "
                "extreme_low < bearish < bullish < extreme_high"
            )

        object.__setattr__(
            self,
            "pcr_bullish_threshold",
            pcr_bullish_threshold,
        )
        object.__setattr__(
            self,
            "pcr_bearish_threshold",
            pcr_bearish_threshold,
        )
        object.__setattr__(
            self,
            "pcr_extreme_high_threshold",
            pcr_extreme_high_threshold,
        )
        object.__setattr__(
            self,
            "pcr_extreme_low_threshold",
            pcr_extreme_low_threshold,
        )

        concentration_high = _require_unit_interval(
            self.oi_concentration_high_ratio,
            "oi_concentration_high_ratio",
        )
        concentration_low = _require_unit_interval(
            self.oi_concentration_low_ratio,
            "oi_concentration_low_ratio",
        )

        if concentration_low >= concentration_high:
            raise ValueError(
                "oi_concentration_low_ratio must be less than "
                "oi_concentration_high_ratio"
            )

        object.__setattr__(
            self,
            "oi_concentration_high_ratio",
            concentration_high,
        )
        object.__setattr__(
            self,
            "oi_concentration_low_ratio",
            concentration_low,
        )

        object.__setattr__(
            self,
            "oi_buildup_minimum_absolute_change",
            _require_non_negative_integer(
                self.oi_buildup_minimum_absolute_change,
                "oi_buildup_minimum_absolute_change",
            ),
        )

        max_pain_near = _require_non_negative_float(
            self.max_pain_near_distance_bps,
            "max_pain_near_distance_bps",
        )
        max_pain_far = _require_positive_float(
            self.max_pain_far_distance_bps,
            "max_pain_far_distance_bps",
        )

        if max_pain_near >= max_pain_far:
            raise ValueError(
                "max_pain_near_distance_bps must be less than "
                "max_pain_far_distance_bps"
            )

        object.__setattr__(
            self,
            "max_pain_near_distance_bps",
            max_pain_near,
        )
        object.__setattr__(
            self,
            "max_pain_far_distance_bps",
            max_pain_far,
        )

        object.__setattr__(
            self,
            "iv_skew_material_difference",
            _require_non_negative_float(
                self.iv_skew_material_difference,
                "iv_skew_material_difference",
            ),
        )

        object.__setattr__(
            self,
            "support_resistance_top_n",
            _require_positive_integer(
                self.support_resistance_top_n,
                "support_resistance_top_n",
            ),
        )

        minimum_valid_metrics = _require_positive_integer(
            self.minimum_valid_metrics,
            "minimum_valid_metrics",
        )

        if minimum_valid_metrics > len(_REQUIRED_METRICS):
            raise ValueError(
                "minimum_valid_metrics must not exceed the number "
                "of required metrics"
            )

        object.__setattr__(
            self,
            "minimum_valid_metrics",
            minimum_valid_metrics,
        )

        bullish_score_threshold = _require_unit_interval(
            self.bullish_score_threshold,
            "bullish_score_threshold",
        )
        bearish_score_threshold = _require_finite_float(
            self.bearish_score_threshold,
            "bearish_score_threshold",
        )

        if not -1.0 <= bearish_score_threshold <= 0.0:
            raise ValueError(
                "bearish_score_threshold must be between -1.0 and 0.0"
            )

        if bullish_score_threshold <= 0.0:
            raise ValueError(
                "bullish_score_threshold must be greater than zero"
            )

        object.__setattr__(
            self,
            "bullish_score_threshold",
            bullish_score_threshold,
        )
        object.__setattr__(
            self,
            "bearish_score_threshold",
            bearish_score_threshold,
        )

        conflict_tolerance = _require_unit_interval(
            self.conflicting_score_tolerance,
            "conflicting_score_tolerance",
        )

        if conflict_tolerance > bullish_score_threshold:
            raise ValueError(
                "conflicting_score_tolerance must not exceed "
                "bullish_score_threshold"
            )

        if conflict_tolerance > abs(bearish_score_threshold):
            raise ValueError(
                "conflicting_score_tolerance must not exceed the "
                "absolute bearish score threshold"
            )

        object.__setattr__(
            self,
            "conflicting_score_tolerance",
            conflict_tolerance,
        )

        object.__setattr__(
            self,
            "insufficient_metrics_behavior",
            _require_behavior(
                self.insufficient_metrics_behavior,
                "insufficient_metrics_behavior",
            ),
        )
        object.__setattr__(
            self,
            "missing_metric_behavior",
            _require_behavior(
                self.missing_metric_behavior,
                "missing_metric_behavior",
            ),
        )
        object.__setattr__(
            self,
            "conflicting_signal_behavior",
            _require_behavior(
                self.conflicting_signal_behavior,
                "conflicting_signal_behavior",
            ),
        )

        if self.execution_mode != self.EXECUTION_MODE:
            raise ValueError("execution_mode must be PAPER")

        if self.live_execution_eligible is not False:
            raise ValueError(
                "live_execution_eligible must remain False"
            )

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def required_metrics(self) -> tuple[str, ...]:
        return _REQUIRED_METRICS

    def metric_weight(self, metric_name: str) -> float:
        normalized_name = _require_non_empty_string(
            metric_name,
            "metric_name",
        ).upper()

        for name, weight in self.metric_weights:
            if name == normalized_name:
                return weight

        raise KeyError(
            f"metric weight is not configured for {normalized_name}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_name": self.policy_name,
            "required_metrics": list(self.required_metrics),
            "metric_weights": [
                [name, weight]
                for name, weight in self.metric_weights
            ],
            "pcr_bullish_threshold": self.pcr_bullish_threshold,
            "pcr_bearish_threshold": self.pcr_bearish_threshold,
            "pcr_extreme_high_threshold": (
                self.pcr_extreme_high_threshold
            ),
            "pcr_extreme_low_threshold": (
                self.pcr_extreme_low_threshold
            ),
            "oi_concentration_high_ratio": (
                self.oi_concentration_high_ratio
            ),
            "oi_concentration_low_ratio": (
                self.oi_concentration_low_ratio
            ),
            "oi_buildup_minimum_absolute_change": (
                self.oi_buildup_minimum_absolute_change
            ),
            "max_pain_near_distance_bps": (
                self.max_pain_near_distance_bps
            ),
            "max_pain_far_distance_bps": (
                self.max_pain_far_distance_bps
            ),
            "iv_skew_material_difference": (
                self.iv_skew_material_difference
            ),
            "support_resistance_top_n": (
                self.support_resistance_top_n
            ),
            "minimum_valid_metrics": self.minimum_valid_metrics,
            "bullish_score_threshold": self.bullish_score_threshold,
            "bearish_score_threshold": self.bearish_score_threshold,
            "conflicting_score_tolerance": (
                self.conflicting_score_tolerance
            ),
            "insufficient_metrics_behavior": (
                self.insufficient_metrics_behavior
            ),
            "missing_metric_behavior": self.missing_metric_behavior,
            "conflicting_signal_behavior": (
                self.conflicting_signal_behavior
            ),
            "execution_mode": self.execution_mode,
            "live_execution_eligible": self.live_execution_eligible,
        }


DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY = (
    OptionChainIntelligencePolicyV1(
        policy_name="INITIAL_CANONICAL_OPTION_CHAIN_INTELLIGENCE_POLICY",
        metric_weights=(
            ("PCR_OPEN_INTEREST", 0.20),
            ("PCR_VOLUME", 0.10),
            ("OI_CONCENTRATION", 0.15),
            ("OI_BUILDUP", 0.20),
            ("MAX_PAIN", 0.10),
            ("IV_SKEW", 0.10),
            ("SUPPORT_RESISTANCE", 0.15),
        ),
        pcr_bullish_threshold=1.10,
        pcr_bearish_threshold=0.90,
        pcr_extreme_high_threshold=1.50,
        pcr_extreme_low_threshold=0.60,
        oi_concentration_high_ratio=0.35,
        oi_concentration_low_ratio=0.15,
        oi_buildup_minimum_absolute_change=1,
        max_pain_near_distance_bps=50.0,
        max_pain_far_distance_bps=200.0,
        iv_skew_material_difference=2.0,
        support_resistance_top_n=3,
        minimum_valid_metrics=4,
        bullish_score_threshold=0.15,
        bearish_score_threshold=-0.15,
        conflicting_score_tolerance=0.05,
        insufficient_metrics_behavior="BLOCK",
        missing_metric_behavior="WARN",
        conflicting_signal_behavior="WARN",
    )
)


__all__ = [
    "DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY",
    "OptionChainIntelligencePolicyV1",
]