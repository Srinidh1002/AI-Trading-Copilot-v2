from __future__ import annotations

from services.contracts.option_chain_intelligence_result_v1 import (
    OptionChainIntelligenceResultV1,
)

from .dashboard_option_intelligence_view_v1 import (
    DashboardOptionIntelligenceViewV1,
)


def _metric_value(
    source: OptionChainIntelligenceResultV1,
    name: str,
) -> float | None:
    try:
        metric = source.metric_by_name(name)
    except KeyError:
        return None

    for attribute in (
        "value",
        "metric_value",
        "numeric_value",
        "score",
    ):
        value = getattr(metric, attribute, None)
        if isinstance(value, bool):
            continue
        if type(value) in (int, float):
            return float(value)
    return None


def _first(values: tuple[float, ...]) -> float | None:
    return values[0] if values else None


def _last(values: tuple[float, ...]) -> float | None:
    return values[-1] if values else None


def project_option_intelligence(
    source: OptionChainIntelligenceResultV1,
) -> DashboardOptionIntelligenceViewV1:
    """Project certified option-chain evidence without recalculation."""

    if type(source) is not OptionChainIntelligenceResultV1:
        raise TypeError(
            "source must be exact OptionChainIntelligenceResultV1"
        )

    return DashboardOptionIntelligenceViewV1(
        source_id=source.option_chain_intelligence_result_id,
        underlying_symbol=source.underlying_symbol,
        exchange=source.exchange,
        status=source.intelligence_status,
        source_updated_at=source.created_at,
        pcr=(
            _metric_value(source, "PCR_OPEN_INTEREST")
            or _metric_value(source, "PCR_VOLUME")
        ),
        directional_bias=source.aggregate_bias,
        flow=None,
        confidence=source.aggregate_strength,
        support=_last(source.support_strikes),
        resistance=_first(source.resistance_strikes),
        max_pain=source.max_pain_strike,
        call_open_interest=None,
        put_open_interest=None,
        atm_delta=None,
        atm_gamma=None,
        atm_theta=None,
        atm_vega=None,
        aggregate_greeks_summary=None,
        blockers=source.blockers,
        warnings=source.warnings,
    )
