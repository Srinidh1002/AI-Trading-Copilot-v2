"""Deterministic open-interest buildup intelligence.

The metric compares aggregate signed change in open interest:

    net_buildup = total PUT change in OI - total CALL change in OI

The normalized metric value is:

    net_buildup / (
        abs(total PUT change in OI)
        + abs(total CALL change in OI)
    )

Interpretation:

- positive imbalance: BULLISH
- negative imbalance: BEARISH
- immaterial or zero imbalance: NEUTRAL

Signed change-in-open-interest values are preserved. Missing values are not
fabricated as zero-valued observations.

This module does not fetch data, choose contracts, rank opportunities, produce
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


OI_BUILDUP_METRIC_NAME: Final[str] = "OI_BUILDUP"


def calculate_oi_buildup(
    *,
    snapshot: OptionChainSnapshotV1,
    policy: OptionChainIntelligencePolicyV1 = (
        DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY
    ),
) -> OptionChainMetricV1:
    """Calculate aggregate signed change-in-OI imbalance."""

    if not isinstance(snapshot, OptionChainSnapshotV1):
        raise TypeError(
            "snapshot must be an OptionChainSnapshotV1"
        )

    if not isinstance(policy, OptionChainIntelligencePolicyV1):
        raise TypeError(
            "policy must be an OptionChainIntelligencePolicyV1"
        )

    call_change_total = 0
    put_change_total = 0
    valid_quote_count = 0
    supporting_strikes: list[float] = []

    for row in snapshot.strike_rows:
        row_used = False

        if row.call is not None:
            call_change = row.call.change_in_open_interest

            if call_change is not None:
                call_change_total += call_change
                valid_quote_count += 1
                row_used = True

        if row.put is not None:
            put_change = row.put.change_in_open_interest

            if put_change is not None:
                put_change_total += put_change
                valid_quote_count += 1
                row_used = True

        if row_used:
            supporting_strikes.append(float(row.strike))

    normalized_supporting_strikes = tuple(supporting_strikes)

    if valid_quote_count == 0:
        return OptionChainMetricV1(
            metric_name=OI_BUILDUP_METRIC_NAME,
            value=None,
            signal="UNAVAILABLE",
            status="UNAVAILABLE",
            sample_size=0,
            parameters=(
                (
                    "minimum_absolute_change",
                    policy.oi_buildup_minimum_absolute_change,
                ),
            ),
            supporting_strikes=(),
            blockers=(
                "change in open interest is unavailable for all quotes",
            ),
            warnings=(),
        )

    net_buildup = put_change_total - call_change_total

    gross_absolute_change = (
        abs(put_change_total)
        + abs(call_change_total)
    )

    if gross_absolute_change == 0:
        normalized_imbalance = 0.0
    else:
        normalized_imbalance = (
            float(net_buildup)
            / float(gross_absolute_change)
        )

    minimum_absolute_change = (
        policy.oi_buildup_minimum_absolute_change
    )

    if abs(net_buildup) < minimum_absolute_change:
        signal = "NEUTRAL"
    elif net_buildup > 0:
        signal = "BULLISH"
    elif net_buildup < 0:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"

    warnings: tuple[str, ...] = ()

    if call_change_total < 0 and put_change_total < 0:
        warnings = (
            "aggregate CALL and PUT open interest are both unwinding",
        )

    status = (
        "VALID_WITH_WARNINGS"
        if warnings
        else "VALID"
    )

    return OptionChainMetricV1(
        metric_name=OI_BUILDUP_METRIC_NAME,
        value=normalized_imbalance,
        signal=signal,
        status=status,
        sample_size=valid_quote_count,
        parameters=(
            ("put_change_total", put_change_total),
            ("call_change_total", call_change_total),
            ("net_buildup", net_buildup),
            (
                "gross_absolute_change",
                gross_absolute_change,
            ),
            (
                "minimum_absolute_change",
                minimum_absolute_change,
            ),
        ),
        supporting_strikes=normalized_supporting_strikes,
        blockers=(),
        warnings=warnings,
    )


__all__ = [
    "OI_BUILDUP_METRIC_NAME",
    "calculate_oi_buildup",
]