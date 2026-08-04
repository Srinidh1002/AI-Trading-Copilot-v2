"""Deterministic option-chain implied-volatility skew intelligence.

The canonical IV-skew metric compares average PUT implied volatility with
average CALL implied volatility across strikes where at least one side has a
valid implied-volatility observation.

Metric value:

    average PUT IV - average CALL IV

Interpretation:

- materially higher PUT IV: BEARISH
- materially higher CALL IV: BULLISH
- difference inside configured threshold: NEUTRAL

A higher PUT IV is treated as bearish option-chain evidence because downside
protection is priced more richly. A higher CALL IV is treated as bullish
evidence because upside optionality is priced more richly.

This module does not fetch data, calculate Greeks, select contracts, rank
opportunities, produce final decisions, calculate risk, or execute orders.
"""

from __future__ import annotations

from typing import Final

from services.contracts.option_chain_intelligence_policy_v1 import (
    DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY,
    OptionChainIntelligencePolicyV1,
)
from services.contracts.option_chain_metric_v1 import OptionChainMetricV1
from services.contracts.option_chain_snapshot_v1 import OptionChainSnapshotV1


IV_SKEW_METRIC_NAME: Final[str] = "IV_SKEW"


def _unavailable_metric(
    *,
    blocker: str,
    sample_size: int,
    supporting_strikes: tuple[float, ...],
    policy: OptionChainIntelligencePolicyV1,
) -> OptionChainMetricV1:
    return OptionChainMetricV1(
        metric_name=IV_SKEW_METRIC_NAME,
        value=None,
        signal="UNAVAILABLE",
        status="UNAVAILABLE",
        sample_size=sample_size,
        parameters=(
            (
                "material_difference",
                policy.iv_skew_material_difference,
            ),
        ),
        supporting_strikes=supporting_strikes,
        blockers=(blocker,),
        warnings=(),
    )


def calculate_iv_skew(
    *,
    snapshot: OptionChainSnapshotV1,
    policy: OptionChainIntelligencePolicyV1 = (
        DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY
    ),
) -> OptionChainMetricV1:
    """Calculate average PUT IV minus average CALL IV."""

    if not isinstance(snapshot, OptionChainSnapshotV1):
        raise TypeError(
            "snapshot must be an OptionChainSnapshotV1"
        )

    if not isinstance(policy, OptionChainIntelligencePolicyV1):
        raise TypeError(
            "policy must be an OptionChainIntelligencePolicyV1"
        )

    call_iv_values: list[float] = []
    put_iv_values: list[float] = []
    supporting_strikes: list[float] = []
    valid_quote_count = 0

    for row in snapshot.strike_rows:
        row_used = False

        if row.call is not None:
            call_iv = row.call.implied_volatility

            if call_iv is not None:
                call_iv_values.append(float(call_iv))
                valid_quote_count += 1
                row_used = True

        if row.put is not None:
            put_iv = row.put.implied_volatility

            if put_iv is not None:
                put_iv_values.append(float(put_iv))
                valid_quote_count += 1
                row_used = True

        if row_used:
            supporting_strikes.append(float(row.strike))

    normalized_supporting_strikes = tuple(supporting_strikes)

    if not call_iv_values and not put_iv_values:
        return _unavailable_metric(
            blocker="implied volatility is unavailable for all quotes",
            sample_size=0,
            supporting_strikes=(),
            policy=policy,
        )

    if not call_iv_values:
        return _unavailable_metric(
            blocker="CALL implied volatility is unavailable",
            sample_size=valid_quote_count,
            supporting_strikes=normalized_supporting_strikes,
            policy=policy,
        )

    if not put_iv_values:
        return _unavailable_metric(
            blocker="PUT implied volatility is unavailable",
            sample_size=valid_quote_count,
            supporting_strikes=normalized_supporting_strikes,
            policy=policy,
        )

    average_call_iv = (
        sum(call_iv_values)
        / len(call_iv_values)
    )
    average_put_iv = (
        sum(put_iv_values)
        / len(put_iv_values)
    )

    skew_difference = (
        average_put_iv
        - average_call_iv
    )

    material_difference = (
        policy.iv_skew_material_difference
    )

    if skew_difference >= material_difference:
        signal = "BEARISH"
    elif skew_difference <= -material_difference:
        signal = "BULLISH"
    else:
        signal = "NEUTRAL"

    warnings: list[str] = []

    if len(call_iv_values) != len(put_iv_values):
        warnings.append(
            "CALL and PUT implied-volatility sample counts differ"
        )

    if len(call_iv_values) < 2 or len(put_iv_values) < 2:
        warnings.append(
            "implied-volatility skew uses fewer than two observations "
            "on at least one option side"
        )

    normalized_warnings = tuple(warnings)

    status = (
        "VALID_WITH_WARNINGS"
        if normalized_warnings
        else "VALID"
    )

    return OptionChainMetricV1(
        metric_name=IV_SKEW_METRIC_NAME,
        value=skew_difference,
        signal=signal,
        status=status,
        sample_size=valid_quote_count,
        parameters=(
            (
                "average_call_iv",
                average_call_iv,
            ),
            (
                "average_put_iv",
                average_put_iv,
            ),
            (
                "call_sample_count",
                len(call_iv_values),
            ),
            (
                "put_sample_count",
                len(put_iv_values),
            ),
            (
                "material_difference",
                material_difference,
            ),
        ),
        supporting_strikes=normalized_supporting_strikes,
        blockers=(),
        warnings=normalized_warnings,
    )


__all__ = [
    "IV_SKEW_METRIC_NAME",
    "calculate_iv_skew",
]