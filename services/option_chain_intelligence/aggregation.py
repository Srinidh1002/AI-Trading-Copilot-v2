"""Canonical option-chain intelligence aggregation.

This module combines already-calculated option-chain metrics into one
provider-neutral intelligence result.

Important guarantees:

- unavailable metric weights are not renormalized
- blocked quality produces zero aggregate strength
- non-directional structural metrics contribute zero directional score
- no option selection, final decision, ranking, risk, or execution behavior
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Final
from uuid import uuid4

from services.contracts.option_chain_intelligence_policy_v1 import (
    DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY,
    OptionChainIntelligencePolicyV1,
)
from services.contracts.option_chain_intelligence_result_v1 import (
    OptionChainIntelligenceResultV1,
)
from services.contracts.option_chain_metric_v1 import OptionChainMetricV1
from services.contracts.option_chain_quality_result_v1 import (
    OptionChainQualityResultV1,
)
from services.contracts.option_chain_snapshot_v1 import (
    OptionChainSnapshotV1,
)


_VALID_METRIC_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "VALID",
        "VALID_WITH_WARNINGS",
    }
)

_ACCEPTED_QUALITY_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "VALID",
        "VALID_WITH_WARNINGS",
    }
)

_DIRECTIONAL_SIGNAL_VALUES: Final[dict[str, float]] = {
    "BULLISH": 1.0,
    "BEARISH": -1.0,
    "NEUTRAL": 0.0,
    "HIGH": 0.0,
    "LOW": 0.0,
    "RISING": 0.0,
    "FALLING": 0.0,
    "BALANCED": 0.0,
    "CONCENTRATED": 0.0,
    "DISPERSED": 0.0,
    "NONE": 0.0,
}

_BLOCKING_QUALITY_STATUS_MAP: Final[dict[str, str]] = {
    "FAILED": "FAILED",
    "UNSUPPORTED": "UNSUPPORTED",
    "MALFORMED": "MALFORMED",
    "FUTURE": "INSUFFICIENT_METRICS",
    "EMPTY": "INSUFFICIENT_METRICS",
    "STALE": "INSUFFICIENT_METRICS",
    "INCOMPLETE": "INSUFFICIENT_METRICS",
}


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _default_result_id_factory() -> str:
    return f"option-chain-intelligence-{uuid4()}"


def _require_timezone_aware_datetime(
    value: datetime,
    field_name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must return a datetime")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must return a timezone-aware datetime")

    return value


def _require_string_tuple(
    value: tuple[str, ...],
    field_name: str,
) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(f"{field_name} must be a tuple")

    normalized: list[str] = []
    seen: set[str] = set()

    for item in value:
        if not isinstance(item, str):
            raise TypeError(f"{field_name} must contain only strings")

        clean_item = item.strip()

        if not clean_item:
            raise ValueError(
                f"{field_name} must not contain empty strings"
            )

        if clean_item in seen:
            continue

        seen.add(clean_item)
        normalized.append(clean_item)

    return tuple(normalized)


def _require_strike_tuple(
    value: tuple[float, ...],
    field_name: str,
) -> tuple[float, ...]:
    if not isinstance(value, tuple):
        raise TypeError(f"{field_name} must be a tuple")

    normalized = tuple(float(strike) for strike in value)

    if any(strike <= 0.0 for strike in normalized):
        raise ValueError(
            f"{field_name} must contain only positive strikes"
        )

    if normalized != tuple(sorted(set(normalized))):
        raise ValueError(
            f"{field_name} must be strictly ascending and unique"
        )

    return normalized


def _merge_messages(
    *groups: tuple[str, ...],
) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()

    for group in groups:
        for message in group:
            if message not in seen:
                seen.add(message)
                merged.append(message)

    return tuple(merged)


def _quality_blocked_result(
    *,
    snapshot: OptionChainSnapshotV1,
    quality_result: OptionChainQualityResultV1,
    metrics: tuple[OptionChainMetricV1, ...],
    created_at: datetime,
    result_id: str,
    support_strikes: tuple[float, ...],
    resistance_strikes: tuple[float, ...],
    max_pain_strike: float | None,
) -> OptionChainIntelligenceResultV1:
    intelligence_status = _BLOCKING_QUALITY_STATUS_MAP.get(
        quality_result.quality_status,
        "FAILED",
    )

    metric_names = tuple(
        metric.metric_name.upper()
        for metric in metrics
    )

    blockers = _merge_messages(
        quality_result.blockers,
        (
            "option-chain quality status does not permit intelligence "
            "aggregation",
        ),
    )

    return OptionChainIntelligenceResultV1(
        option_chain_intelligence_result_id=result_id,
        created_at=created_at,
        option_chain_snapshot_id=snapshot.option_chain_snapshot_id,
        option_chain_quality_result_id=(
            quality_result.option_chain_quality_result_id
        ),
        underlying_symbol=snapshot.underlying_symbol,
        exchange=snapshot.exchange,
        expiry=snapshot.expiry,
        metrics=metrics,
        intelligence_status=intelligence_status,
        aggregate_bias="UNAVAILABLE",
        aggregate_strength=0.0,
        bullish_metrics=(),
        bearish_metrics=(),
        neutral_metrics=(),
        unavailable_metrics=metric_names,
        valid_metric_count=sum(
            metric.status in _VALID_METRIC_STATUSES
            for metric in metrics
        ),
        unavailable_metric_count=sum(
            metric.status not in _VALID_METRIC_STATUSES
            for metric in metrics
        ),
        support_strikes=support_strikes,
        resistance_strikes=resistance_strikes,
        max_pain_strike=max_pain_strike,
        blockers=blockers,
        warnings=quality_result.warnings,
        execution_mode="PAPER",
        live_execution_eligible=False,
    )


def aggregate_option_chain_intelligence(
    *,
    snapshot: OptionChainSnapshotV1,
    quality_result: OptionChainQualityResultV1,
    metrics: tuple[OptionChainMetricV1, ...],
    support_strikes: tuple[float, ...] = (),
    resistance_strikes: tuple[float, ...] = (),
    max_pain_strike: float | None = None,
    policy: OptionChainIntelligencePolicyV1 = (
        DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY
    ),
    clock: Callable[[], datetime] | None = None,
    option_chain_intelligence_result_id_factory: (
        Callable[[], str] | None
    ) = None,
) -> OptionChainIntelligenceResultV1:
    """Aggregate canonical option-chain metrics without weight renormalization."""

    if not isinstance(snapshot, OptionChainSnapshotV1):
        raise TypeError(
            "snapshot must be an OptionChainSnapshotV1"
        )

    if not isinstance(quality_result, OptionChainQualityResultV1):
        raise TypeError(
            "quality_result must be an OptionChainQualityResultV1"
        )

    if not isinstance(policy, OptionChainIntelligencePolicyV1):
        raise TypeError(
            "policy must be an OptionChainIntelligencePolicyV1"
        )

    if not isinstance(metrics, tuple):
        raise TypeError("metrics must be a tuple")

    for metric in metrics:
        if not isinstance(metric, OptionChainMetricV1):
            raise TypeError(
                "metrics must contain only OptionChainMetricV1"
            )

    metric_names = tuple(
        metric.metric_name.upper()
        for metric in metrics
    )

    if len(metric_names) != len(set(metric_names)):
        raise ValueError(
            "metrics must not contain duplicate metric names"
        )

    if (
        quality_result.option_chain_snapshot_id
        != snapshot.option_chain_snapshot_id
    ):
        raise ValueError(
            "quality result must reference the supplied snapshot"
        )

    if (
        quality_result.underlying_symbol
        != snapshot.underlying_symbol
        or quality_result.exchange != snapshot.exchange
        or quality_result.expiry != snapshot.expiry
    ):
        raise ValueError(
            "snapshot and quality result identities must match"
        )

    normalized_support_strikes = _require_strike_tuple(
        support_strikes,
        "support_strikes",
    )
    normalized_resistance_strikes = _require_strike_tuple(
        resistance_strikes,
        "resistance_strikes",
    )

    if max_pain_strike is not None:
        max_pain_strike = float(max_pain_strike)

        if max_pain_strike <= 0.0:
            raise ValueError(
                "max_pain_strike must be positive when supplied"
            )

    resolved_clock = clock or _default_clock
    resolved_id_factory = (
        option_chain_intelligence_result_id_factory
        or _default_result_id_factory
    )

    created_at = _require_timezone_aware_datetime(
        resolved_clock(),
        "clock",
    )

    result_id = resolved_id_factory()

    if not isinstance(result_id, str) or not result_id.strip():
        raise ValueError(
            "option-chain intelligence result ID must be non-empty"
        )

    if quality_result.quality_status not in _ACCEPTED_QUALITY_STATUSES:
        return _quality_blocked_result(
            snapshot=snapshot,
            quality_result=quality_result,
            metrics=metrics,
            created_at=created_at,
            result_id=result_id.strip(),
            support_strikes=normalized_support_strikes,
            resistance_strikes=normalized_resistance_strikes,
            max_pain_strike=max_pain_strike,
        )

    metrics_by_name = {
        metric.metric_name.upper(): metric
        for metric in metrics
    }

    missing_metric_names = tuple(
        metric_name
        for metric_name in policy.required_metrics
        if metric_name not in metrics_by_name
    )

    valid_metrics = tuple(
        metric
        for metric in metrics
        if metric.status in _VALID_METRIC_STATUSES
    )

    unavailable_metrics_objects = tuple(
        metric
        for metric in metrics
        if metric.status not in _VALID_METRIC_STATUSES
    )

    bullish_metric_names: list[str] = []
    bearish_metric_names: list[str] = []
    neutral_metric_names: list[str] = []
    unavailable_metric_names: list[str] = []

    weighted_score = 0.0

    for metric_name in policy.required_metrics:
        metric = metrics_by_name.get(metric_name)

        if metric is None:
            continue

        if metric.status not in _VALID_METRIC_STATUSES:
            unavailable_metric_names.append(metric_name)
            continue

        if metric.signal == "BULLISH":
            bullish_metric_names.append(metric_name)
        elif metric.signal == "BEARISH":
            bearish_metric_names.append(metric_name)
        else:
            neutral_metric_names.append(metric_name)

        directional_value = _DIRECTIONAL_SIGNAL_VALUES.get(
            metric.signal,
            0.0,
        )

        weighted_score += (
            policy.metric_weight(metric_name)
            * directional_value
        )

    valid_metric_count = len(valid_metrics)
    unavailable_metric_count = len(
           unavailable_metrics_objects
    )

    blockers: list[str] = []
    warnings: list[str] = list(quality_result.warnings)

    for metric in metrics:
        warnings.extend(metric.warnings)

        if metric.status not in _VALID_METRIC_STATUSES:
            warnings.extend(metric.blockers)

    if missing_metric_names:
        message = (
            "required option-chain metrics are missing: "
            + ", ".join(missing_metric_names)
        )

        if policy.missing_metric_behavior == "BLOCK":
            blockers.append(message)
        elif policy.missing_metric_behavior == "WARN":
            warnings.append(message)

    if valid_metric_count < policy.minimum_valid_metrics:
        message = (
            "valid option-chain metric count is below the configured "
            "minimum"
        )

        if policy.insufficient_metrics_behavior == "BLOCK":
            blockers.append(message)
        elif policy.insufficient_metrics_behavior == "WARN":
            warnings.append(message)

    has_bullish = bool(bullish_metric_names)
    has_bearish = bool(bearish_metric_names)

    is_low_score_conflict = (
        has_bullish
        and has_bearish
        and abs(weighted_score)
        <= policy.conflicting_score_tolerance
    )

    if blockers:
        intelligence_status = "INSUFFICIENT_METRICS"
        aggregate_bias = "UNAVAILABLE"
        aggregate_strength = 0.0

    elif is_low_score_conflict:
        conflict_message = (
            "bullish and bearish option-chain metrics conflict within "
            "the configured score tolerance"
        )

        if policy.conflicting_signal_behavior == "BLOCK":
            intelligence_status = "CONFLICTING"
            aggregate_bias = "MIXED"
            aggregate_strength = abs(weighted_score)
            blockers.append(conflict_message)

        elif policy.conflicting_signal_behavior == "WARN":
            intelligence_status = "CONFLICTING"
            aggregate_bias = "MIXED"
            aggregate_strength = abs(weighted_score)
            warnings.append(conflict_message)

        else:
            intelligence_status = (
                "READY_WITH_WARNINGS"
                if warnings
                else "READY"
            )
            aggregate_bias = "NEUTRAL"
            aggregate_strength = abs(weighted_score)

    else:
        if weighted_score >= policy.bullish_score_threshold:
            aggregate_bias = "BULLISH"
        elif weighted_score <= policy.bearish_score_threshold:
            aggregate_bias = "BEARISH"
        else:
            aggregate_bias = "NEUTRAL"

        aggregate_strength = abs(weighted_score)

        intelligence_status = (
            "READY_WITH_WARNINGS"
            if warnings
            else "READY"
        )

    normalized_blockers = _require_string_tuple(
        tuple(blockers),
        "blockers",
    )
    normalized_warnings = _require_string_tuple(
        tuple(warnings),
        "warnings",
    )

    return OptionChainIntelligenceResultV1(
        option_chain_intelligence_result_id=result_id.strip(),
        created_at=created_at,
        option_chain_snapshot_id=snapshot.option_chain_snapshot_id,
        option_chain_quality_result_id=(
            quality_result.option_chain_quality_result_id
        ),
        underlying_symbol=snapshot.underlying_symbol,
        exchange=snapshot.exchange,
        expiry=snapshot.expiry,
        metrics=metrics,
        intelligence_status=intelligence_status,
        aggregate_bias=aggregate_bias,
        aggregate_strength=aggregate_strength,
        bullish_metrics=tuple(bullish_metric_names),
        bearish_metrics=tuple(bearish_metric_names),
        neutral_metrics=tuple(neutral_metric_names),
        unavailable_metrics=tuple(unavailable_metric_names),
        valid_metric_count=valid_metric_count,
        unavailable_metric_count=unavailable_metric_count,
        support_strikes=normalized_support_strikes,
        resistance_strikes=normalized_resistance_strikes,
        max_pain_strike=max_pain_strike,
        blockers=normalized_blockers,
        warnings=normalized_warnings,
        execution_mode="PAPER",
        live_execution_eligible=False,
    )


__all__ = [
    "aggregate_option_chain_intelligence",
]