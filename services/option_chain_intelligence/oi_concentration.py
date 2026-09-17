"""Deterministic open-interest concentration intelligence.

The concentration ratio is:

    largest combined strike OI / total combined chain OI

For each strike, available CALL and PUT open interest are added together.
Missing sides remain absent and are not fabricated as quotes.

This module does not fetch data, rank opportunities, select contracts, create
trading decisions, calculate risk, or execute orders.
"""

from __future__ import annotations

from typing import Final

from services.contracts.option_chain_intelligence_policy_v1 import (
    DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY,
    OptionChainIntelligencePolicyV1,
)
from services.contracts.option_chain_metric_v1 import OptionChainMetricV1
from services.contracts.option_chain_snapshot_v1 import OptionChainSnapshotV1


OI_CONCENTRATION_METRIC_NAME: Final[str] = "OI_CONCENTRATION"


def _classify_concentration(
    *,
    concentration_ratio: float,
    policy: OptionChainIntelligencePolicyV1,
) -> str:
    if concentration_ratio >= policy.oi_concentration_high_ratio:
        return "CONCENTRATED"

    if concentration_ratio <= policy.oi_concentration_low_ratio:
        return "DISPERSED"

    return "BALANCED"


def calculate_oi_concentration(
    *,
    snapshot: OptionChainSnapshotV1,
    policy: OptionChainIntelligencePolicyV1 = (
        DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY
    ),
) -> OptionChainMetricV1:
    """Calculate combined CALL-and-PUT OI concentration by strike."""

    if not isinstance(snapshot, OptionChainSnapshotV1):
        raise TypeError(
            "snapshot must be an OptionChainSnapshotV1"
        )

    if not isinstance(policy, OptionChainIntelligencePolicyV1):
        raise TypeError(
            "policy must be an OptionChainIntelligencePolicyV1"
        )

    strike_totals: list[tuple[float, int]] = []
    valid_quote_count = 0

    for row in snapshot.strike_rows:
        strike_total = 0
        has_available_oi = False

        if row.call is not None:
            call_oi = row.call.open_interest

            if call_oi is not None:
                strike_total += call_oi
                valid_quote_count += 1
                has_available_oi = True

        if row.put is not None:
            put_oi = row.put.open_interest

            if put_oi is not None:
                strike_total += put_oi
                valid_quote_count += 1
                has_available_oi = True

        if has_available_oi:
            strike_totals.append(
                (float(row.strike), strike_total)
            )

    total_open_interest = sum(
        strike_total
        for _, strike_total in strike_totals
    )

    supporting_strikes = tuple(
        strike
        for strike, _ in strike_totals
    )

    if total_open_interest <= 0:
        return OptionChainMetricV1(
            metric_name=OI_CONCENTRATION_METRIC_NAME,
            value=None,
            signal="UNAVAILABLE",
            status="UNAVAILABLE",
            sample_size=valid_quote_count,
            parameters=(
                (
                    "high_ratio",
                    policy.oi_concentration_high_ratio,
                ),
                (
                    "low_ratio",
                    policy.oi_concentration_low_ratio,
                ),
            ),
            supporting_strikes=supporting_strikes,
            blockers=(
                "total chain open interest is zero or unavailable",
            ),
            warnings=(),
        )

    maximum_strike_total = max(
        strike_total
        for _, strike_total in strike_totals
    )

    concentration_ratio = (
        float(maximum_strike_total)
        / float(total_open_interest)
    )

    dominant_strikes = tuple(
        strike
        for strike, strike_total in strike_totals
        if strike_total == maximum_strike_total
    )

    signal = _classify_concentration(
        concentration_ratio=concentration_ratio,
        policy=policy,
    )

    warnings: tuple[str, ...] = ()

    if len(dominant_strikes) > 1:
        warnings = (
            "multiple strikes share the maximum combined open interest",
        )

    status = (
        "VALID_WITH_WARNINGS"
        if warnings
        else "VALID"
    )

    return OptionChainMetricV1(
        metric_name=OI_CONCENTRATION_METRIC_NAME,
        value=concentration_ratio,
        signal=signal,
        status=status,
        sample_size=valid_quote_count,
        parameters=(
            ("total_open_interest", total_open_interest),
            (
                "maximum_strike_open_interest",
                maximum_strike_total,
            ),
            (
                "high_ratio",
                policy.oi_concentration_high_ratio,
            ),
            (
                "low_ratio",
                policy.oi_concentration_low_ratio,
            ),
            (
                "dominant_strike_count",
                len(dominant_strikes),
            ),
        ),
        supporting_strikes=dominant_strikes,
        blockers=(),
        warnings=warnings,
    )


__all__ = [
    "OI_CONCENTRATION_METRIC_NAME",
    "calculate_oi_concentration",
]