"""Deterministic option-chain support and resistance intelligence.

Canonical interpretation:

- PUT open interest at or below the underlying contributes support evidence.
- CALL open interest at or above the underlying contributes resistance
  evidence.
- The strongest configured number of strikes on each side are selected.
- Missing option sides remain absent and are never fabricated.

Directional balance:

    (selected support OI - selected resistance OI)
    ------------------------------------------------
    (selected support OI + selected resistance OI)

Positive balance is BULLISH, negative balance is BEARISH, and zero is NEUTRAL.

This is option-chain evidence only. It does not select an option contract,
produce a final decision, rank opportunities, calculate risk, or execute
orders.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Final

from services.contracts.option_chain_intelligence_policy_v1 import (
    DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY,
    OptionChainIntelligencePolicyV1,
)
from services.contracts.option_chain_metric_v1 import OptionChainMetricV1
from services.contracts.option_chain_snapshot_v1 import OptionChainSnapshotV1


SUPPORT_RESISTANCE_METRIC_NAME: Final[str] = "SUPPORT_RESISTANCE"


@dataclass(frozen=True, slots=True)
class SupportResistanceAnalysis:
    """Canonical support/resistance calculation output."""

    metric: OptionChainMetricV1
    support_strikes: tuple[float, ...]
    resistance_strikes: tuple[float, ...]


def _unavailable_analysis(
    *,
    blocker: str,
    sample_size: int,
    policy: OptionChainIntelligencePolicyV1,
) -> SupportResistanceAnalysis:
    metric = OptionChainMetricV1(
        metric_name=SUPPORT_RESISTANCE_METRIC_NAME,
        value=None,
        signal="UNAVAILABLE",
        status="UNAVAILABLE",
        sample_size=sample_size,
        parameters=(
            (
                "top_n",
                policy.support_resistance_top_n,
            ),
        ),
        supporting_strikes=(),
        blockers=(blocker,),
        warnings=(),
    )

    return SupportResistanceAnalysis(
        metric=metric,
        support_strikes=(),
        resistance_strikes=(),
    )


def _select_support_candidates(
    *,
    candidates: list[tuple[float, int]],
    underlying_value: float,
    top_n: int,
) -> tuple[tuple[float, int], ...]:
    """Rank support by OI, then proximity, then higher strike."""

    ranked = sorted(
        candidates,
        key=lambda item: (
            -item[1],
            abs(underlying_value - item[0]),
            -item[0],
        ),
    )

    return tuple(ranked[:top_n])


def _select_resistance_candidates(
    *,
    candidates: list[tuple[float, int]],
    underlying_value: float,
    top_n: int,
) -> tuple[tuple[float, int], ...]:
    """Rank resistance by OI, then proximity, then lower strike."""

    ranked = sorted(
        candidates,
        key=lambda item: (
            -item[1],
            abs(item[0] - underlying_value),
            item[0],
        ),
    )

    return tuple(ranked[:top_n])


def analyze_support_resistance(
    *,
    snapshot: OptionChainSnapshotV1,
    policy: OptionChainIntelligencePolicyV1 = (
        DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY
    ),
) -> SupportResistanceAnalysis:
    """Calculate canonical support and resistance levels."""

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
        return _unavailable_analysis(
            blocker="underlying value is unavailable",
            sample_size=0,
            policy=policy,
        )

    if not isfinite(underlying_value) or underlying_value <= 0.0:
        return _unavailable_analysis(
            blocker="underlying value must be finite and positive",
            sample_size=0,
            policy=policy,
        )

    support_candidates: list[tuple[float, int]] = []
    resistance_candidates: list[tuple[float, int]] = []
    valid_quote_count = 0

    for row in snapshot.strike_rows:
        strike = float(row.strike)

        if row.put is not None:
            put_open_interest = row.put.open_interest

            if put_open_interest is not None:
                valid_quote_count += 1

                if strike <= underlying_value:
                    support_candidates.append(
                        (strike, put_open_interest)
                    )

        if row.call is not None:
            call_open_interest = row.call.open_interest

            if call_open_interest is not None:
                valid_quote_count += 1

                if strike >= underlying_value:
                    resistance_candidates.append(
                        (strike, call_open_interest)
                    )

    if not support_candidates and not resistance_candidates:
        return _unavailable_analysis(
            blocker=(
                "no eligible support or resistance open-interest "
                "observations are available"
            ),
            sample_size=valid_quote_count,
            policy=policy,
        )

    selected_support = _select_support_candidates(
        candidates=support_candidates,
        underlying_value=underlying_value,
        top_n=policy.support_resistance_top_n,
    )
    selected_resistance = _select_resistance_candidates(
        candidates=resistance_candidates,
        underlying_value=underlying_value,
        top_n=policy.support_resistance_top_n,
    )

    support_strikes = tuple(
        sorted(strike for strike, _ in selected_support)
    )
    resistance_strikes = tuple(
        sorted(strike for strike, _ in selected_resistance)
    )

    support_open_interest = sum(
        open_interest
        for _, open_interest in selected_support
    )
    resistance_open_interest = sum(
        open_interest
        for _, open_interest in selected_resistance
    )

    selected_total_open_interest = (
        support_open_interest
        + resistance_open_interest
    )

    if selected_total_open_interest <= 0:
        return _unavailable_analysis(
            blocker=(
                "selected support and resistance open interest is zero"
            ),
            sample_size=valid_quote_count,
            policy=policy,
        )

    directional_balance = (
        float(
            support_open_interest
            - resistance_open_interest
        )
        / float(selected_total_open_interest)
    )

    if directional_balance > 0.0:
        signal = "BULLISH"
    elif directional_balance < 0.0:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"

    warnings: list[str] = []

    if not selected_support:
        warnings.append(
            "no eligible support strike was available"
        )

    if not selected_resistance:
        warnings.append(
            "no eligible resistance strike was available"
        )

    strongest_support = (
        selected_support[0][0]
        if selected_support
        else 0.0
    )
    strongest_resistance = (
        selected_resistance[0][0]
        if selected_resistance
        else 0.0
    )

    all_selected_strikes = tuple(
        sorted(
            set(support_strikes)
            | set(resistance_strikes)
        )
    )

    normalized_warnings = tuple(warnings)

    status = (
        "VALID_WITH_WARNINGS"
        if normalized_warnings
        else "VALID"
    )

    metric = OptionChainMetricV1(
        metric_name=SUPPORT_RESISTANCE_METRIC_NAME,
        value=directional_balance,
        signal=signal,
        status=status,
        sample_size=valid_quote_count,
        parameters=(
            ("underlying_value", underlying_value),
            (
                "top_n",
                policy.support_resistance_top_n,
            ),
            (
                "support_candidate_count",
                len(support_candidates),
            ),
            (
                "resistance_candidate_count",
                len(resistance_candidates),
            ),
            (
                "selected_support_count",
                len(selected_support),
            ),
            (
                "selected_resistance_count",
                len(selected_resistance),
            ),
            (
                "support_open_interest",
                support_open_interest,
            ),
            (
                "resistance_open_interest",
                resistance_open_interest,
            ),
            (
                "strongest_support",
                strongest_support,
            ),
            (
                "strongest_resistance",
                strongest_resistance,
            ),
        ),
        supporting_strikes=all_selected_strikes,
        blockers=(),
        warnings=normalized_warnings,
    )

    return SupportResistanceAnalysis(
        metric=metric,
        support_strikes=support_strikes,
        resistance_strikes=resistance_strikes,
    )


def calculate_support_resistance(
    *,
    snapshot: OptionChainSnapshotV1,
    policy: OptionChainIntelligencePolicyV1 = (
        DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY
    ),
) -> OptionChainMetricV1:
    """Return only the canonical support/resistance metric."""

    return analyze_support_resistance(
        snapshot=snapshot,
        policy=policy,
    ).metric


__all__ = [
    "SUPPORT_RESISTANCE_METRIC_NAME",
    "SupportResistanceAnalysis",
    "analyze_support_resistance",
    "calculate_support_resistance",
]