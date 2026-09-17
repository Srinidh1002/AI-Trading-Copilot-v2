"""Deterministic put-call-ratio intelligence.

This module calculates open-interest PCR and volume PCR from an already
normalized canonical option-chain snapshot.

It does not fetch data, select contracts, rank opportunities, produce trading
decisions, calculate risk, or execute orders.
"""

from __future__ import annotations

from typing import Final

from services.contracts.option_chain_intelligence_policy_v1 import (
    DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY,
    OptionChainIntelligencePolicyV1,
)
from services.contracts.option_chain_metric_v1 import OptionChainMetricV1
from services.contracts.option_chain_snapshot_v1 import OptionChainSnapshotV1


PCR_OPEN_INTEREST_METRIC_NAME: Final[str] = "PCR_OPEN_INTEREST"
PCR_VOLUME_METRIC_NAME: Final[str] = "PCR_VOLUME"


def _classify_pcr(
    *,
    value: float,
    policy: OptionChainIntelligencePolicyV1,
) -> tuple[str, str, tuple[str, ...]]:
    """Return signal, status, and warnings for one PCR value."""

    if value >= policy.pcr_extreme_high_threshold:
        return (
            "BULLISH",
            "VALID_WITH_WARNINGS",
            ("PCR is above the configured extreme-high threshold",),
        )

    if value <= policy.pcr_extreme_low_threshold:
        return (
            "BEARISH",
            "VALID_WITH_WARNINGS",
            ("PCR is below the configured extreme-low threshold",),
        )

    if value >= policy.pcr_bullish_threshold:
        return "BULLISH", "VALID", ()

    if value <= policy.pcr_bearish_threshold:
        return "BEARISH", "VALID", ()

    return "NEUTRAL", "VALID", ()


def _unavailable_metric(
    *,
    metric_name: str,
    sample_size: int,
    supporting_strikes: tuple[float, ...],
    denominator_name: str,
) -> OptionChainMetricV1:
    return OptionChainMetricV1(
        metric_name=metric_name,
        value=None,
        signal="UNAVAILABLE",
        status="UNAVAILABLE",
        sample_size=sample_size,
        parameters=(
            ("denominator", denominator_name),
        ),
        supporting_strikes=supporting_strikes,
        blockers=(
            f"{denominator_name} total is zero or unavailable",
        ),
        warnings=(),
    )


def _calculate_ratio_metric(
    *,
    snapshot: OptionChainSnapshotV1,
    metric_name: str,
    quote_field: str,
    denominator_name: str,
    policy: OptionChainIntelligencePolicyV1,
) -> OptionChainMetricV1:
    call_total = 0
    put_total = 0
    valid_quote_count = 0
    supporting_strikes: list[float] = []

    for row in snapshot.strike_rows:
        row_used = False

        if row.call is not None:
            call_value = getattr(row.call, quote_field)

            if call_value is not None:
                call_total += call_value
                valid_quote_count += 1
                row_used = True

        if row.put is not None:
            put_value = getattr(row.put, quote_field)

            if put_value is not None:
                put_total += put_value
                valid_quote_count += 1
                row_used = True

        if row_used:
            supporting_strikes.append(float(row.strike))

    normalized_supporting_strikes = tuple(supporting_strikes)

    if call_total <= 0:
        return _unavailable_metric(
            metric_name=metric_name,
            sample_size=valid_quote_count,
            supporting_strikes=normalized_supporting_strikes,
            denominator_name=denominator_name,
        )

    value = float(put_total) / float(call_total)

    signal, status, warnings = _classify_pcr(
        value=value,
        policy=policy,
    )

    return OptionChainMetricV1(
        metric_name=metric_name,
        value=value,
        signal=signal,
        status=status,
        sample_size=valid_quote_count,
        parameters=(
            ("put_total", put_total),
            ("call_total", call_total),
            (
                "bullish_threshold",
                policy.pcr_bullish_threshold,
            ),
            (
                "bearish_threshold",
                policy.pcr_bearish_threshold,
            ),
            (
                "extreme_high_threshold",
                policy.pcr_extreme_high_threshold,
            ),
            (
                "extreme_low_threshold",
                policy.pcr_extreme_low_threshold,
            ),
        ),
        supporting_strikes=normalized_supporting_strikes,
        blockers=(),
        warnings=warnings,
    )


def calculate_open_interest_pcr(
    *,
    snapshot: OptionChainSnapshotV1,
    policy: OptionChainIntelligencePolicyV1 = (
        DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY
    ),
) -> OptionChainMetricV1:
    """Calculate put-call ratio from canonical open-interest values."""

    if not isinstance(snapshot, OptionChainSnapshotV1):
        raise TypeError(
            "snapshot must be an OptionChainSnapshotV1"
        )

    if not isinstance(policy, OptionChainIntelligencePolicyV1):
        raise TypeError(
            "policy must be an OptionChainIntelligencePolicyV1"
        )

    return _calculate_ratio_metric(
        snapshot=snapshot,
        metric_name=PCR_OPEN_INTEREST_METRIC_NAME,
        quote_field="open_interest",
        denominator_name="call_open_interest",
        policy=policy,
    )


def calculate_volume_pcr(
    *,
    snapshot: OptionChainSnapshotV1,
    policy: OptionChainIntelligencePolicyV1 = (
        DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY
    ),
) -> OptionChainMetricV1:
    """Calculate put-call ratio from canonical volume values."""

    if not isinstance(snapshot, OptionChainSnapshotV1):
        raise TypeError(
            "snapshot must be an OptionChainSnapshotV1"
        )

    if not isinstance(policy, OptionChainIntelligencePolicyV1):
        raise TypeError(
            "policy must be an OptionChainIntelligencePolicyV1"
        )

    return _calculate_ratio_metric(
        snapshot=snapshot,
        metric_name=PCR_VOLUME_METRIC_NAME,
        quote_field="volume",
        denominator_name="call_volume",
        policy=policy,
    )


def calculate_pcr_metrics(
    *,
    snapshot: OptionChainSnapshotV1,
    policy: OptionChainIntelligencePolicyV1 = (
        DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY
    ),
) -> tuple[OptionChainMetricV1, OptionChainMetricV1]:
    """Calculate canonical open-interest and volume PCR metrics."""

    return (
        calculate_open_interest_pcr(
            snapshot=snapshot,
            policy=policy,
        ),
        calculate_volume_pcr(
            snapshot=snapshot,
            policy=policy,
        ),
    )


__all__ = [
    "PCR_OPEN_INTEREST_METRIC_NAME",
    "PCR_VOLUME_METRIC_NAME",
    "calculate_open_interest_pcr",
    "calculate_pcr_metrics",
    "calculate_volume_pcr",
]