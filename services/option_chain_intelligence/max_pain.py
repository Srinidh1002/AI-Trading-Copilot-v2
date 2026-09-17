"""Deterministic option-chain max-pain intelligence.

For every available strike, this module calculates the aggregate intrinsic
payout that option writers would owe if the underlying expired at that strike.

For candidate settlement strike S:

    CALL pain = sum(max(S - call_strike, 0) * call_open_interest)
    PUT pain  = sum(max(put_strike - S, 0) * put_open_interest)

The strike with the minimum aggregate payout is the canonical max-pain strike.

When multiple strikes have the same minimum payout, the deterministic selected
strike is:

1. The tied strike nearest to the current underlying value.
2. The lower strike when distance is also tied.

All tied minimum-pain strikes remain available in supporting_strikes.

This module does not fetch option-chain data, select an option contract, rank
opportunities, create a final decision, calculate position risk, or execute
orders.
"""

from __future__ import annotations

from math import isfinite
from typing import Final

from services.contracts.option_chain_intelligence_policy_v1 import (
    DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY,
    OptionChainIntelligencePolicyV1,
)
from services.contracts.option_chain_metric_v1 import OptionChainMetricV1
from services.contracts.option_chain_snapshot_v1 import OptionChainSnapshotV1


MAX_PAIN_METRIC_NAME: Final[str] = "MAX_PAIN"


def _unavailable_metric(
    *,
    blocker: str,
    sample_size: int,
    policy: OptionChainIntelligencePolicyV1,
) -> OptionChainMetricV1:
    return OptionChainMetricV1(
        metric_name=MAX_PAIN_METRIC_NAME,
        value=None,
        signal="UNAVAILABLE",
        status="UNAVAILABLE",
        sample_size=sample_size,
        parameters=(
            (
                "near_distance_bps",
                policy.max_pain_near_distance_bps,
            ),
            (
                "far_distance_bps",
                policy.max_pain_far_distance_bps,
            ),
        ),
        supporting_strikes=(),
        blockers=(blocker,),
        warnings=(),
    )


def _classify_max_pain_position(
    *,
    max_pain_strike: float,
    underlying_value: float,
    distance_bps: float,
    policy: OptionChainIntelligencePolicyV1,
) -> tuple[str, str, tuple[str, ...]]:
    """Classify max-pain position relative to the current underlying."""

    if distance_bps <= policy.max_pain_near_distance_bps:
        return "NEUTRAL", "VALID", ()

    if max_pain_strike > underlying_value:
        signal = "BULLISH"
    elif max_pain_strike < underlying_value:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"

    if distance_bps >= policy.max_pain_far_distance_bps:
        return (
            signal,
            "VALID_WITH_WARNINGS",
            (
                "max-pain strike is far from the current underlying value",
            ),
        )

    return signal, "VALID", ()


def calculate_max_pain(
    *,
    snapshot: OptionChainSnapshotV1,
    policy: OptionChainIntelligencePolicyV1 = (
        DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY
    ),
) -> OptionChainMetricV1:
    """Calculate the deterministic canonical max-pain strike."""

    if not isinstance(snapshot, OptionChainSnapshotV1):
        raise TypeError(
            "snapshot must be an OptionChainSnapshotV1"
        )

    if not isinstance(policy, OptionChainIntelligencePolicyV1):
        raise TypeError(
            "policy must be an OptionChainIntelligencePolicyV1"
        )

    underlying_value = snapshot.underlying_value

    if underlying_value is None:
        return _unavailable_metric(
            blocker="underlying value is unavailable",
            sample_size=0,
            policy=policy,
        )

    if not isfinite(underlying_value) or underlying_value <= 0.0:
        return _unavailable_metric(
            blocker="underlying value must be finite and positive",
            sample_size=0,
            policy=policy,
        )

    call_open_interest: list[tuple[float, int]] = []
    put_open_interest: list[tuple[float, int]] = []
    valid_quote_count = 0
    total_open_interest = 0

    candidate_strikes = tuple(
        float(row.strike)
        for row in snapshot.strike_rows
    )

    if not candidate_strikes:
        return _unavailable_metric(
            blocker="option chain contains no candidate strikes",
            sample_size=0,
            policy=policy,
        )

    for row in snapshot.strike_rows:
        strike = float(row.strike)

        if row.call is not None:
            call_oi = row.call.open_interest

            if call_oi is not None:
                call_open_interest.append((strike, call_oi))
                valid_quote_count += 1
                total_open_interest += call_oi

        if row.put is not None:
            put_oi = row.put.open_interest

            if put_oi is not None:
                put_open_interest.append((strike, put_oi))
                valid_quote_count += 1
                total_open_interest += put_oi

    if valid_quote_count == 0:
        return _unavailable_metric(
            blocker="open interest is unavailable for all option quotes",
            sample_size=0,
            policy=policy,
        )

    if total_open_interest <= 0:
        return _unavailable_metric(
            blocker="total option-chain open interest is zero",
            sample_size=valid_quote_count,
            policy=policy,
        )

    payout_by_strike: list[tuple[float, float]] = []

    for settlement_strike in candidate_strikes:
        call_pain = sum(
            max(settlement_strike - option_strike, 0.0)
            * open_interest
            for option_strike, open_interest in call_open_interest
        )

        put_pain = sum(
            max(option_strike - settlement_strike, 0.0)
            * open_interest
            for option_strike, open_interest in put_open_interest
        )

        total_pain = float(call_pain + put_pain)

        payout_by_strike.append(
            (settlement_strike, total_pain)
        )

    minimum_total_pain = min(
        total_pain
        for _, total_pain in payout_by_strike
    )

    tied_max_pain_strikes = tuple(
        strike
        for strike, total_pain in payout_by_strike
        if total_pain == minimum_total_pain
    )

    selected_max_pain_strike = min(
        tied_max_pain_strikes,
        key=lambda strike: (
            abs(strike - underlying_value),
            strike,
        ),
    )

    signed_distance_bps = (
        (selected_max_pain_strike - underlying_value)
        / underlying_value
        * 10_000.0
    )
    absolute_distance_bps = abs(signed_distance_bps)

    signal, status, classification_warnings = (
        _classify_max_pain_position(
            max_pain_strike=selected_max_pain_strike,
            underlying_value=underlying_value,
            distance_bps=absolute_distance_bps,
            policy=policy,
        )
    )

    warnings = list(classification_warnings)

    if len(tied_max_pain_strikes) > 1:
        warnings.append(
            "multiple strikes share the minimum aggregate option payout"
        )

    normalized_warnings = tuple(warnings)

    if normalized_warnings:
        status = "VALID_WITH_WARNINGS"

    return OptionChainMetricV1(
        metric_name=MAX_PAIN_METRIC_NAME,
        value=selected_max_pain_strike,
        signal=signal,
        status=status,
        sample_size=valid_quote_count,
        parameters=(
            ("underlying_value", underlying_value),
            ("minimum_total_pain", minimum_total_pain),
            (
                "signed_distance_bps",
                signed_distance_bps,
            ),
            (
                "absolute_distance_bps",
                absolute_distance_bps,
            ),
            (
                "near_distance_bps",
                policy.max_pain_near_distance_bps,
            ),
            (
                "far_distance_bps",
                policy.max_pain_far_distance_bps,
            ),
            (
                "tied_minimum_count",
                len(tied_max_pain_strikes),
            ),
            (
                "total_open_interest",
                total_open_interest,
            ),
        ),
        supporting_strikes=tied_max_pain_strikes,
        blockers=(),
        warnings=normalized_warnings,
    )


__all__ = [
    "MAX_PAIN_METRIC_NAME",
    "calculate_max_pain",
]