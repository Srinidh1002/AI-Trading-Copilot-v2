"""Canonical option-chain intelligence result contract.

This contract represents deterministic option-chain evidence only. It does not
represent a trading decision, option selection, opportunity ranking, risk
result, or execution request.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from typing import Any, ClassVar

from services.contracts.option_chain_metric_v1 import OptionChainMetricV1


_CANONICAL_MARKETS = frozenset(
    {
        ("NIFTY", "NSE"),
        ("BANKNIFTY", "NSE"),
        ("FINNIFTY", "NSE"),
        ("SENSEX", "BSE"),
    }
)

_ALLOWED_STATUSES = frozenset(
    {
        "READY",
        "READY_WITH_WARNINGS",
        "INSUFFICIENT_METRICS",
        "CONFLICTING",
        "MALFORMED",
        "UNSUPPORTED",
        "FAILED",
        "UNAVAILABLE",
    }
)

_BLOCKING_STATUSES = frozenset(
    {
        "INSUFFICIENT_METRICS",
        "MALFORMED",
        "UNSUPPORTED",
        "FAILED",
    }
)

_ALLOWED_BIASES = frozenset(
    {
        "BULLISH",
        "BEARISH",
        "NEUTRAL",
        "MIXED",
        "UNAVAILABLE",
    }
)

_VALID_METRIC_STATUSES = frozenset(
    {
        "VALID",
        "VALID_WITH_WARNINGS",
    }
)


def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    normalized = value.strip()

    if not normalized:
        raise ValueError(f"{field_name} must not be empty")

    return normalized


def _require_timezone_aware_datetime(
    value: Any,
    field_name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")

    return value


def _require_date(value: Any, field_name: str) -> date:
    if isinstance(value, datetime) or not isinstance(value, date):
        raise TypeError(f"{field_name} must be a date")

    return value


def _require_string_tuple(
    value: Any,
    field_name: str,
) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(f"{field_name} must be a tuple")

    normalized: list[str] = []
    seen: set[str] = set()

    for item in value:
        clean_item = _require_non_empty_string(
            item,
            f"{field_name} item",
        ).upper()

        if clean_item in seen:
            raise ValueError(
                f"{field_name} must not contain duplicate values"
            )

        seen.add(clean_item)
        normalized.append(clean_item)

    return tuple(normalized)


def _require_positive_strike_tuple(
    value: Any,
    field_name: str,
) -> tuple[float, ...]:
    if not isinstance(value, tuple):
        raise TypeError(f"{field_name} must be a tuple")

    normalized: list[float] = []
    seen: set[float] = set()

    for strike in value:
        if isinstance(strike, bool) or not isinstance(
            strike,
            (int, float),
        ):
            raise TypeError(
                f"{field_name} must contain finite numeric values"
            )

        normalized_strike = float(strike)

        if not isfinite(normalized_strike):
            raise ValueError(
                f"{field_name} must contain finite values"
            )

        if normalized_strike <= 0.0:
            raise ValueError(
                f"{field_name} must contain positive strike values"
            )

        if normalized_strike in seen:
            raise ValueError(
                f"{field_name} must not contain duplicate strikes"
            )

        seen.add(normalized_strike)
        normalized.append(normalized_strike)

    if tuple(normalized) != tuple(sorted(normalized)):
        raise ValueError(
            f"{field_name} must be strictly ascending"
        )

    return tuple(normalized)


def _require_optional_positive_float(
    value: Any,
    field_name: str,
) -> float | None:
    if value is None:
        return None

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(
            f"{field_name} must be a finite positive number or None"
        )

    normalized = float(value)

    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite")

    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be greater than zero")

    return normalized


def _require_non_negative_integer(
    value: Any,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")

    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")

    return value


def _require_strength(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("aggregate_strength must be a finite number")

    normalized = float(value)

    if not isfinite(normalized):
        raise ValueError("aggregate_strength must be finite")

    if not 0.0 <= normalized <= 1.0:
        raise ValueError(
            "aggregate_strength must be between 0.0 and 1.0"
        )

    return normalized


@dataclass(frozen=True, slots=True)
class OptionChainIntelligenceResultV1:
    """Immutable aggregate option-chain intelligence evidence."""

    SCHEMA_VERSION: ClassVar[str] = (
        "option_chain_intelligence_result.v1"
    )
    EXECUTION_MODE: ClassVar[str] = "PAPER"
    LIVE_EXECUTION_ELIGIBLE: ClassVar[bool] = False

    option_chain_intelligence_result_id: str
    created_at: datetime

    option_chain_snapshot_id: str | None
    option_chain_quality_result_id: str | None

    underlying_symbol: str
    exchange: str
    expiry: date | None

    metrics: tuple[OptionChainMetricV1, ...]

    intelligence_status: str
    aggregate_bias: str
    aggregate_strength: float

    bullish_metrics: tuple[str, ...]
    bearish_metrics: tuple[str, ...]
    neutral_metrics: tuple[str, ...]
    unavailable_metrics: tuple[str, ...]

    valid_metric_count: int
    unavailable_metric_count: int

    support_strikes: tuple[float, ...] = ()
    resistance_strikes: tuple[float, ...] = ()
    max_pain_strike: float | None = None

    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    reasons: tuple[str, ...] = ()
    source_status: str = "AVAILABLE"

    def __post_init__(self) -> None:
        result_id = _require_non_empty_string(
            self.option_chain_intelligence_result_id,
            "option_chain_intelligence_result_id",
        )
        object.__setattr__(
            self,
            "option_chain_intelligence_result_id",
            result_id,
        )

        created_at = _require_timezone_aware_datetime(
            self.created_at,
            "created_at",
        )
        object.__setattr__(self, "created_at", created_at)

        status = _require_non_empty_string(self.intelligence_status, "intelligence_status").upper()
        if status not in _ALLOWED_STATUSES:
            raise ValueError(f"unsupported intelligence_status: {status}")
        object.__setattr__(self, "intelligence_status", status)
        if status == "UNAVAILABLE":
            if any(value is not None for value in (self.option_chain_snapshot_id, self.option_chain_quality_result_id, self.expiry)):
                raise ValueError("UNAVAILABLE result must not carry snapshot, quality, or expiry")
            if self.metrics or any((self.bullish_metrics, self.bearish_metrics, self.neutral_metrics, self.unavailable_metrics)):
                raise ValueError("UNAVAILABLE result must not carry analytical metrics")
            if self.valid_metric_count != 0 or self.unavailable_metric_count != 0 or self.support_strikes or self.resistance_strikes or self.max_pain_strike is not None:
                raise ValueError("UNAVAILABLE result must not carry derived values")
            symbol = _require_non_empty_string(self.underlying_symbol, "underlying_symbol").upper()
            exchange = _require_non_empty_string(self.exchange, "exchange").upper()
            if (symbol, exchange) not in _CANONICAL_MARKETS or self.aggregate_bias != "UNAVAILABLE" or self.aggregate_strength != 0.0:
                raise ValueError("invalid UNAVAILABLE option intelligence")
            blockers = _require_string_tuple(self.blockers, "blockers")
            if not blockers:
                raise ValueError("UNAVAILABLE result requires blockers")
            object.__setattr__(self, "underlying_symbol", symbol)
            object.__setattr__(self, "exchange", exchange)
            object.__setattr__(self, "blockers", blockers)
            object.__setattr__(self, "warnings", _require_string_tuple(self.warnings, "warnings"))
            object.__setattr__(self, "reasons", _require_string_tuple(self.reasons, "reasons"))
            object.__setattr__(self, "source_status", _require_non_empty_string(self.source_status, "source_status").upper())
            return

        snapshot_id = _require_non_empty_string(
            self.option_chain_snapshot_id,
            "option_chain_snapshot_id",
        )
        quality_result_id = _require_non_empty_string(
            self.option_chain_quality_result_id,
            "option_chain_quality_result_id",
        )

        object.__setattr__(
            self,
            "option_chain_snapshot_id",
            snapshot_id,
        )
        object.__setattr__(
            self,
            "option_chain_quality_result_id",
            quality_result_id,
        )

        underlying_symbol = _require_non_empty_string(
            self.underlying_symbol,
            "underlying_symbol",
        ).upper()
        exchange = _require_non_empty_string(
            self.exchange,
            "exchange",
        ).upper()

        if (underlying_symbol, exchange) not in _CANONICAL_MARKETS:
            raise ValueError(
                "underlying_symbol and exchange must be one of the "
                "four canonical market identities"
            )

        object.__setattr__(
            self,
            "underlying_symbol",
            underlying_symbol,
        )
        object.__setattr__(self, "exchange", exchange)

        expiry = _require_date(self.expiry, "expiry")
        object.__setattr__(self, "expiry", expiry)

        if not isinstance(self.metrics, tuple):
            raise TypeError("metrics must be a tuple")

        metric_names: list[str] = []
        seen_metric_names: set[str] = set()

        for metric in self.metrics:
            if not isinstance(metric, OptionChainMetricV1):
                raise TypeError(
                    "metrics must contain only OptionChainMetricV1"
                )

            metric_name = metric.metric_name.upper()

            if metric_name in seen_metric_names:
                raise ValueError(
                    "metrics must not contain duplicate metric names"
                )

            seen_metric_names.add(metric_name)
            metric_names.append(metric_name)

        status = _require_non_empty_string(
            self.intelligence_status,
            "intelligence_status",
        ).upper()

        if status not in _ALLOWED_STATUSES:
            raise ValueError(
                f"unsupported intelligence_status: {status}"
            )

        object.__setattr__(
            self,
            "intelligence_status",
            status,
        )

        aggregate_bias = _require_non_empty_string(
            self.aggregate_bias,
            "aggregate_bias",
        ).upper()

        if aggregate_bias not in _ALLOWED_BIASES:
            raise ValueError(
                f"unsupported aggregate_bias: {aggregate_bias}"
            )

        object.__setattr__(
            self,
            "aggregate_bias",
            aggregate_bias,
        )

        aggregate_strength = _require_strength(
            self.aggregate_strength
        )
        object.__setattr__(
            self,
            "aggregate_strength",
            aggregate_strength,
        )

        bullish_metrics = _require_string_tuple(
            self.bullish_metrics,
            "bullish_metrics",
        )
        bearish_metrics = _require_string_tuple(
            self.bearish_metrics,
            "bearish_metrics",
        )
        neutral_metrics = _require_string_tuple(
            self.neutral_metrics,
            "neutral_metrics",
        )
        unavailable_metrics = _require_string_tuple(
            self.unavailable_metrics,
            "unavailable_metrics",
        )

        object.__setattr__(
            self,
            "bullish_metrics",
            bullish_metrics,
        )
        object.__setattr__(
            self,
            "bearish_metrics",
            bearish_metrics,
        )
        object.__setattr__(
            self,
            "neutral_metrics",
            neutral_metrics,
        )
        object.__setattr__(
            self,
            "unavailable_metrics",
            unavailable_metrics,
        )

        primary_groups = (
            bullish_metrics,
            bearish_metrics,
            neutral_metrics,
            unavailable_metrics,
        )

        classified_names: list[str] = [
            name
            for group in primary_groups
            for name in group
        ]

        if len(classified_names) != len(set(classified_names)):
            raise ValueError(
                "metric classification tuples must not overlap"
            )

        if set(classified_names) != set(metric_names):
            raise ValueError(
                "every metric must appear exactly once in a primary "
                "classification tuple"
            )

        valid_metric_count = _require_non_negative_integer(
            self.valid_metric_count,
            "valid_metric_count",
        )
        unavailable_metric_count = _require_non_negative_integer(
            self.unavailable_metric_count,
            "unavailable_metric_count",
        )

        expected_valid_count = sum(
            metric.status in _VALID_METRIC_STATUSES
            for metric in self.metrics
        )
        expected_unavailable_count = (
            len(self.metrics) - expected_valid_count
        )

        if valid_metric_count != expected_valid_count:
            raise ValueError(
                "valid_metric_count must reconcile with metrics"
            )

        if unavailable_metric_count != expected_unavailable_count:
            raise ValueError(
                "unavailable_metric_count must reconcile with metrics"
            )

        if valid_metric_count + unavailable_metric_count != len(
            self.metrics
        ):
            raise ValueError(
                "metric counts must reconcile with metrics length"
            )

        object.__setattr__(
            self,
            "valid_metric_count",
            valid_metric_count,
        )
        object.__setattr__(
            self,
            "unavailable_metric_count",
            unavailable_metric_count,
        )

        support_strikes = _require_positive_strike_tuple(
            self.support_strikes,
            "support_strikes",
        )
        resistance_strikes = _require_positive_strike_tuple(
            self.resistance_strikes,
            "resistance_strikes",
        )

        object.__setattr__(
            self,
            "support_strikes",
            support_strikes,
        )
        object.__setattr__(
            self,
            "resistance_strikes",
            resistance_strikes,
        )

        max_pain_strike = _require_optional_positive_float(
            self.max_pain_strike,
            "max_pain_strike",
        )
        object.__setattr__(
            self,
            "max_pain_strike",
            max_pain_strike,
        )

        blockers = _require_string_tuple(
            self.blockers,
            "blockers",
        )
        warnings = _require_string_tuple(
            self.warnings,
            "warnings",
        )

        object.__setattr__(self, "blockers", blockers)
        object.__setattr__(self, "warnings", warnings)
        object.__setattr__(self, "reasons", _require_string_tuple(self.reasons, "reasons"))
        object.__setattr__(self, "source_status", _require_non_empty_string(self.source_status, "source_status").upper())

        if status == "READY":
            if blockers:
                raise ValueError(
                    "READY results must not contain blockers"
                )

            if warnings:
                raise ValueError(
                    "READY results must not contain warnings"
                )

            if aggregate_bias == "UNAVAILABLE":
                raise ValueError(
                    "READY results must not use UNAVAILABLE bias"
                )

            if unavailable_metrics:
                raise ValueError(
                    "READY results must not contain unavailable metrics"
                )

        if status == "READY_WITH_WARNINGS":
            if blockers:
                raise ValueError(
                    "READY_WITH_WARNINGS results must not contain blockers"
                )

            if not warnings:
                raise ValueError(
                    "READY_WITH_WARNINGS results require warnings"
                )

            if aggregate_bias == "UNAVAILABLE":
                raise ValueError(
                    "READY_WITH_WARNINGS results must not use "
                    "UNAVAILABLE bias"
                )

        if status == "CONFLICTING":
            if not blockers and not warnings:
                raise ValueError(
                    "CONFLICTING results require a blocker or warning"
                )

            if aggregate_bias not in {"MIXED", "NEUTRAL"}:
                raise ValueError(
                    "CONFLICTING results must use MIXED or NEUTRAL bias"
                )

        if status in _BLOCKING_STATUSES:
            if not blockers:
                raise ValueError(
                    f"{status} results require at least one blocker"
                )

            if aggregate_bias != "UNAVAILABLE":
                raise ValueError(
                    f"{status} results must use UNAVAILABLE bias"
                )

            if aggregate_strength != 0.0:
                raise ValueError(
                    f"{status} results must use zero aggregate strength"
                )

        if aggregate_bias == "UNAVAILABLE" and aggregate_strength != 0.0:
            raise ValueError(
                "UNAVAILABLE bias must use zero aggregate strength"
            )

        if aggregate_bias == "BULLISH" and not bullish_metrics:
            raise ValueError(
                "BULLISH bias requires at least one bullish metric"
            )

        if aggregate_bias == "BEARISH" and not bearish_metrics:
            raise ValueError(
                "BEARISH bias requires at least one bearish metric"
            )

        if aggregate_bias == "MIXED":
            if not bullish_metrics or not bearish_metrics:
                raise ValueError(
                    "MIXED bias requires both bullish and bearish metrics"
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

    def metric_by_name(
        self,
        metric_name: str,
    ) -> OptionChainMetricV1:
        normalized_name = _require_non_empty_string(
            metric_name,
            "metric_name",
        ).upper()

        for metric in self.metrics:
            if metric.metric_name.upper() == normalized_name:
                return metric

        raise KeyError(
            f"metric not found: {normalized_name}"
        )

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic primitive-only serialization."""

        return {
            "schema_version": self.schema_version,
            "option_chain_intelligence_result_id": (
                self.option_chain_intelligence_result_id
            ),
            "created_at": self.created_at.isoformat(),
            "option_chain_snapshot_id": self.option_chain_snapshot_id,
            "option_chain_quality_result_id": (
                self.option_chain_quality_result_id
            ),
            "underlying_symbol": self.underlying_symbol,
            "exchange": self.exchange,
            "expiry": self.expiry.isoformat() if self.expiry is not None else None,
            "metrics": [
                metric.to_dict()
                for metric in self.metrics
            ],
            "intelligence_status": self.intelligence_status,
            "aggregate_bias": self.aggregate_bias,
            "aggregate_strength": self.aggregate_strength,
            "bullish_metrics": list(self.bullish_metrics),
            "bearish_metrics": list(self.bearish_metrics),
            "neutral_metrics": list(self.neutral_metrics),
            "unavailable_metrics": list(
                self.unavailable_metrics
            ),
            "valid_metric_count": self.valid_metric_count,
            "unavailable_metric_count": (
                self.unavailable_metric_count
            ),
            "support_strikes": list(self.support_strikes),
            "resistance_strikes": list(
                self.resistance_strikes
            ),
            "max_pain_strike": self.max_pain_strike,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "reasons": list(self.reasons),
            "source_status": self.source_status,
            "execution_mode": self.execution_mode,
            "live_execution_eligible": (
                self.live_execution_eligible
            ),
        }


__all__ = [
    "OptionChainIntelligenceResultV1",
]
