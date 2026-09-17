"""Concrete, provider-free bindings for the repository canonical engines."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime

from services.analysis.live_canonical_evidence_engines import (
    LiveCanonicalEvidenceEnginesV1,
)
from services.analysis.market_analysis_candidate_adapters import (
    adapt_technical_pillar_evidence,
)
from services.analysis.market_analysis_option_external_adapters import (
    adapt_option_external_pillar_evidence,
)
from services.analysis.market_analysis_pillar_aggregation import (
    PILLAR_ORDER,
    aggregate_market_analysis_pillars,
)
from services.contracts.market_regime_input_v1 import MarketRegimeInputV1
from services.contracts.option_contract_ranking_result_v1 import (
    OptionContractRankingResultV1,
)
from services.data_quality.candle_quality import (
    evaluate_market_candle_series_quality,
)
from services.market_regime.broader import (
    evaluate_broader_market_regime_component,
)
from services.market_regime.external import (
    evaluate_external_context_regime_component,
)
from services.market_regime.service import evaluate_market_regime
from services.market_regime.technical import (
    evaluate_technical_regime_component,
)
from services.multi_timeframe.pipeline import (
    build_canonical_multi_timeframe_snapshot,
)
from services.multi_timeframe.quality import (
    evaluate_multi_timeframe_quality,
)
from services.option_chain_intelligence.intelligence_pipeline import (
    build_canonical_option_chain_intelligence,
    build_unavailable_option_chain_intelligence,
)
from services.option_chain_intelligence.quality import (
    evaluate_option_chain_quality,
)
from services.option_contract_ranking.ranking_pipeline import (
    build_canonical_option_contract_ranking,
)
from services.technical_intelligence.pipeline import (
    build_canonical_technical_intelligence,
)


_VALID_OPTION_METRIC_STATUSES = {
    "VALID",
    "VALID_WITH_WARNINGS",
}

_TECHNICAL_PILLARS = {
    "price_action",
    "candlestick",
    "chart_pattern",
    "volume",
    "volatility",
}

_OPTION_METRIC_PILLARS = {
    "oi": ("OI_CONCENTRATION",),
    "oi_change": ("OI_BUILDUP",),
    "pcr": (
        "PCR_OPEN_INTEREST",
        "PCR_VOLUME",
    ),
    "support_resistance": (
        "SUPPORT_RESISTANCE",
    ),
    "max_pain": ("MAX_PAIN",),
    "iv": ("IV_SKEW",),
}

_OPTION_AVAILABILITY_METADATA_KEY = (
    "live_option_evidence_availability"
)


def _series(observation):
    return tuple(observation.candle_series)


def _data_quality(
    observation,
    evaluated_at,
):
    series = next(
        (
            item
            for item in _series(observation)
            if item.timeframe == "5m"
        ),
        None,
    )

    if series is None:
        raise ValueError(
            "5m candle series is unavailable"
        )

    return evaluate_market_candle_series_quality(
        series,
        clock=lambda: evaluated_at,
        quality_result_id_factory=lambda: (
            f"live-quality:{series.series_id}"
        ),
    )


def _multi_timeframe(
    observation,
    quality,
    evaluated_at,
):
    snapshot, _ = (
        build_canonical_multi_timeframe_snapshot(
            candle_series_by_timeframe=(
                _series(observation)
            ),
            clock=lambda: evaluated_at,
            snapshot_id_factory=lambda: (
                "live-mtf:"
                f"{observation.spot.symboltoken}:"
                f"{evaluated_at.isoformat()}"
            ),
            multi_timeframe_quality_result_id_factory=(
                lambda: (
                    "live-mtf-quality:"
                    f"{observation.spot.symboltoken}:"
                    f"{evaluated_at.isoformat()}"
                )
            ),
        )
    )

    return snapshot


def _technical(
    observation,
    snapshot,
    evaluated_at,
):
    quality = evaluate_multi_timeframe_quality(
        snapshot,
        clock=lambda: evaluated_at,
        quality_result_id_factory=lambda: (
            "live-mtf-quality:"
            f"{snapshot.multi_timeframe_snapshot_id}"
        ),
    )

    return build_canonical_technical_intelligence(
        candle_series_by_timeframe=(
            _series(observation)
        ),
        multi_timeframe_snapshot=snapshot,
        multi_timeframe_quality_result=quality,
        clock=lambda: evaluated_at,
        technical_intelligence_result_id_factory=(
            lambda: (
                "live-technical:"
                f"{snapshot.multi_timeframe_snapshot_id}"
            )
        ),
    )


def _regime(
    technical,
    session,
    evaluated_at,
    broader_market=None,
    external_context=None,
):
    component = (
        evaluate_technical_regime_component(
            underlying_symbol=(
                technical.underlying_symbol
            ),
            exchange=technical.exchange,
            technical_context=technical,
            created_at=evaluated_at,
            result_id=(
                "live-technical-regime:"
                f"{technical.technical_intelligence_result_id}"
            ),
        )
    )

    broader_component = (
        evaluate_broader_market_regime_component(
            underlying_symbol=(
                technical.underlying_symbol
            ),
            exchange=technical.exchange,
            broader_market_context=broader_market,
            policy=None,
            created_at=evaluated_at,
            result_id=(
                "live-broader-regime:"
                f"{technical.technical_intelligence_result_id}"
            ),
        )
        if broader_market is not None
        else None
    )

    external_component = (
        evaluate_external_context_regime_component(
            underlying_symbol=(
                technical.underlying_symbol
            ),
            exchange=technical.exchange,
            external_market_context=external_context,
            policy=None,
            created_at=evaluated_at,
            result_id=(
                "live-external-regime:"
                f"{technical.technical_intelligence_result_id}"
            ),
        )
    )

    return evaluate_market_regime(
        MarketRegimeInputV1(
            market_regime_input_id=(
                "live-regime:"
                f"{technical.technical_intelligence_result_id}"
            ),
            created_at=evaluated_at,
            underlying_symbol=(
                technical.underlying_symbol
            ),
            exchange=technical.exchange,
            technical_intelligence=technical,
            technical_regime_component=component,
            broader_market_intelligence=(
                broader_market
            ),
            broader_market_regime_component=(
                broader_component
            ),
            external_market_context=external_context,
            external_context_regime_component=(
                external_component
            ),
            market_session_validation=session,
            source_timestamps={
                "technical": technical.created_at,
                "session": session.market_timestamp,
            },
        )
    )


def _option_chain(
    options,
    evaluated_at,
):
    if options.snapshot is None:
        return (
            build_unavailable_option_chain_intelligence(
                underlying_symbol=(
                    options.underlying_symbol
                ),
                exchange=options.exchange,
                option_exchange=(
                    options.option_exchange
                ),
                evaluated_at=evaluated_at,
                blockers=options.blockers,
                warnings=options.warnings,
                reasons=(
                    "Captured option chain is unavailable.",
                ),
            )
        )

    quality = evaluate_option_chain_quality(
        snapshot=options.snapshot,
        clock=lambda: evaluated_at,
        option_chain_quality_result_id_factory=(
            lambda: (
                "live-option-quality:"
                f"{options.snapshot.option_chain_snapshot_id}"
            )
        ),
    )

    return build_canonical_option_chain_intelligence(
        snapshot=options.snapshot,
        quality_result=quality,
        clock=lambda: evaluated_at,
        option_chain_intelligence_result_id_factory=(
            lambda: (
                "live-option:"
                f"{options.snapshot.option_chain_snapshot_id}"
            )
        ),
    )


def _contract_availability(options):
    universe = options.universe

    if universe is None:
        return {
            "contract_count": 0,
            "greeks_complete_count": 0,
            "premium_count": 0,
            "spread_count": 0,
        }

    contracts = tuple(universe.contracts)

    greeks_complete_count = 0
    premium_count = 0
    spread_count = 0

    for contract in contracts:
        metadata = contract.metadata

        if not isinstance(metadata, Mapping):
            metadata = {}

        if all(
            metadata.get(name) is not None
            for name in (
                "delta",
                "gamma",
                "theta",
                "vega",
            )
        ):
            greeks_complete_count += 1

        if contract.last_price is not None:
            premium_count += 1

        if (
            contract.bid_price is not None
            and contract.ask_price is not None
        ):
            spread_count += 1

    return {
        "contract_count": len(contracts),
        "greeks_complete_count": (
            greeks_complete_count
        ),
        "premium_count": premium_count,
        "spread_count": spread_count,
    }


def _with_option_availability(
    ranking,
    options,
):
    metadata = dict(ranking.metadata)

    metadata[
        _OPTION_AVAILABILITY_METADATA_KEY
    ] = _contract_availability(options)

    return replace(
        ranking,
        metadata=metadata,
    )


def _contract_ranking(
    intelligence,
    options,
    evaluated_at,
):
    if options.universe is None:
        ranking = OptionContractRankingResultV1(
            ranking_id=(
                "live-ranking-unavailable:"
                f"{intelligence.option_chain_intelligence_result_id}"
            ),
            ranked_at=evaluated_at,
            universe_id=None,
            intelligence_result_id=(
                intelligence.option_chain_intelligence_result_id
            ),
            underlying_symbol=(
                intelligence.underlying_symbol
            ),
            exchange=intelligence.exchange,
            directional_bias="UNAVAILABLE",
            required_option_type=None,
            ranking_status="INSUFFICIENT_DATA",
            blockers=(
                intelligence.blockers
                + (
                    "OPTION_CONTRACT_UNIVERSE_UNAVAILABLE",
                )
            ),
            warnings=intelligence.warnings,
        )

        return _with_option_availability(
            ranking,
            options,
        )

    ranking = build_canonical_option_contract_ranking(
        intelligence_result=intelligence,
        universe=options.universe,
        now=evaluated_at,
        ranking_id_factory=lambda: (
            "live-ranking:"
            f"{options.universe.universe_id}"
        ),
    )

    return _with_option_availability(
        ranking,
        options,
    )


def _messages(values):
    return tuple(
        dict.fromkeys(
            str(value).strip()
            for value in values
            if str(value).strip()
        )
    )


def _metric_evidence(
    option_chain,
    metric_names,
):
    metrics = []

    for name in metric_names:
        try:
            metric = option_chain.metric_by_name(
                name
            )
        except KeyError:
            metric = None

        metrics.append(
            (
                name,
                metric,
            )
        )

    ready = all(
        metric is not None
        and metric.status
        in _VALID_OPTION_METRIC_STATUSES
        for _, metric in metrics
    )

    blockers = _messages(
        blocker
        for _, metric in metrics
        if metric is not None
        for blocker in metric.blockers
    )

    warnings = _messages(
        warning
        for _, metric in metrics
        if metric is not None
        for warning in metric.warnings
    )

    summary = {
        "metric_statuses": {
            name: (
                metric.status
                if metric is not None
                else "UNAVAILABLE"
            )
            for name, metric in metrics
        },
        "metric_values": {
            name: (
                metric.value
                if metric is not None
                else None
            )
            for name, metric in metrics
        },
        "metric_signals": {
            name: (
                metric.signal
                if metric is not None
                else "UNAVAILABLE"
            )
            for name, metric in metrics
        },
        "blockers": blockers,
        "warnings": warnings,
    }

    return adapt_option_external_pillar_evidence(
        "READY" if ready else "UNAVAILABLE",
        (
            (
                option_chain
                .option_chain_intelligence_result_id,
            )
            if ready
            else ()
        ),
        {
            "source": (
                "canonical_option_chain_metric"
            ),
            "metrics": tuple(metric_names),
        },
        summary,
    )


def _availability_summary(ranking):
    metadata = ranking.metadata

    if not isinstance(metadata, Mapping):
        return {
            "contract_count": 0,
            "greeks_complete_count": 0,
            "premium_count": 0,
            "spread_count": 0,
        }

    value = metadata.get(
        _OPTION_AVAILABILITY_METADATA_KEY
    )

    if not isinstance(value, Mapping):
        return {
            "contract_count": 0,
            "greeks_complete_count": 0,
            "premium_count": 0,
            "spread_count": 0,
        }

    return {
        "contract_count": int(
            value.get(
                "contract_count",
                0,
            )
            or 0
        ),
        "greeks_complete_count": int(
            value.get(
                "greeks_complete_count",
                0,
            )
            or 0
        ),
        "premium_count": int(
            value.get(
                "premium_count",
                0,
            )
            or 0
        ),
        "spread_count": int(
            value.get(
                "spread_count",
                0,
            )
            or 0
        ),
    }


def _contract_field_evidence(
    ranking,
    field_name,
):
    availability = _availability_summary(
        ranking
    )

    contract_count = availability[
        "contract_count"
    ]

    count_field = {
        "greeks": "greeks_complete_count",
        "premium_behavior": "premium_count",
        "liquidity_spread": "spread_count",
    }[field_name]

    available_count = availability[
        count_field
    ]

    ready = (
        contract_count > 0
        and available_count == contract_count
    )

    source_ids = (
        (ranking.universe_id,)
        if ready
        and ranking.universe_id is not None
        else ()
    )

    return adapt_option_external_pillar_evidence(
        "READY" if ready else "UNAVAILABLE",
        source_ids,
        {
            "source": (
                "canonical_option_contract_universe"
            ),
            "field": field_name,
        },
        {
            "contract_count": contract_count,
            "available_count": available_count,
        },
    )


def _pillars(
    observation,
    option_chain,
    ranking,
    evaluated_at,
):
    candle_ids = tuple(
        series.series_id
        for series in observation.candle_series
    )

    market_ready = (
        bool(candle_ids)
        and not observation.blockers
    )

    technical = adapt_technical_pillar_evidence(
        "READY"
        if market_ready
        else "UNAVAILABLE",
        candle_ids
        if market_ready
        else (),
        {
            "source": (
                "canonical_candle_series"
            )
        },
        (
            {
                "series_ids": candle_ids,
            }
            if market_ready
            else {
                "blockers": (
                    observation.blockers
                ),
            }
        ),
    )

    pillars = {}

    for name in PILLAR_ORDER:
        if name in _TECHNICAL_PILLARS:
            pillars[name] = technical
            continue

        metric_names = (
            _OPTION_METRIC_PILLARS.get(
                name
            )
        )

        if metric_names is not None:
            pillars[name] = _metric_evidence(
                option_chain,
                metric_names,
            )
            continue

        if name in {
            "greeks",
            "premium_behavior",
            "liquidity_spread",
        }:
            pillars[name] = (
                _contract_field_evidence(
                    ranking,
                    name,
                )
            )
            continue

        raise ValueError(
            f"unsupported pillar: {name}"
        )

    return aggregate_market_analysis_pillars(
        pillars=pillars,
        evaluated_at=evaluated_at,
    )


def build_default_live_canonical_evidence_engines():
    return LiveCanonicalEvidenceEnginesV1(
        _data_quality,
        _multi_timeframe,
        _technical,
        _regime,
        _option_chain,
        _contract_ranking,
        _pillars,
    )
