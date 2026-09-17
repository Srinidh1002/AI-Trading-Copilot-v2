"""Provider-free construction of truthful fourteen-pillar contribution records."""
from __future__ import annotations

from datetime import datetime

from services.analysis.market_analysis_pillar_aggregation import PILLAR_ORDER, MarketAnalysisPillarAggregationResultV1
from services.contracts.market_analysis_pillar_contribution_v1 import MarketAnalysisPillarContributionCollectionV1, MarketAnalysisPillarContributionV1
from services.contracts.option_chain_intelligence_result_v1 import OptionChainIntelligenceResultV1
from services.contracts.option_contract_ranking_result_v1 import OptionContractRankingResultV1
from services.market.angel_live_observation_normalizer import AngelLiveMarketObservationV1


_CANDLE_PILLARS = frozenset(("price_action", "candlestick", "chart_pattern", "volume", "volatility"))
_OPTION_CHAIN_PILLARS = frozenset(("oi", "oi_change", "pcr", "support_resistance", "max_pain", "iv", "greeks"))


def _messages(summary: object, name: str) -> tuple[str, ...]:
    if not isinstance(summary, dict):
        return ()
    value = summary.get(name, ())
    return tuple(item for item in value if isinstance(item, str) and item.strip()) if isinstance(value, (tuple, list)) else ()


def _candle_source(observation: AngelLiveMarketObservationV1):
    series = next((item for item in observation.candle_series if item.timeframe == "5m"), None)
    if series is None:
        return (None, None, None, None)
    timestamp = series.candles[-1].end_at if series.candles else None
    provider = series.candles[-1].provenance.provider if series.candles else None
    return ("MarketCandleSeriesV1", series.series_id, provider, timestamp)


def _option_source(name: str, option_chain: OptionChainIntelligenceResultV1, ranking: OptionContractRankingResultV1):
    if name in _OPTION_CHAIN_PILLARS:
        return ("OptionChainIntelligenceResultV1", option_chain.option_chain_intelligence_result_id, None, None)
    return ("OptionContractRankingResultV1", ranking.ranking_id, None, ranking.ranked_at)


def build_market_analysis_pillar_contributions(*, cycle_id: str, observation_id: str, observation: AngelLiveMarketObservationV1, option_chain: OptionChainIntelligenceResultV1, contract_ranking: OptionContractRankingResultV1, pillars: MarketAnalysisPillarAggregationResultV1, evaluated_at: datetime) -> MarketAnalysisPillarContributionCollectionV1:
    """Expose existing aggregation truth without changing candidate scoring or policy."""
    if type(observation) is not AngelLiveMarketObservationV1 or type(option_chain) is not OptionChainIntelligenceResultV1 or type(contract_ranking) is not OptionContractRankingResultV1 or type(pillars) is not MarketAnalysisPillarAggregationResultV1:
        raise TypeError("exact canonical evidence inputs")
    identity = (observation.spot.underlying_symbol, observation.spot.exchange)
    if (option_chain.underlying_symbol, option_chain.exchange) != identity or (contract_ranking.underlying_symbol, contract_ranking.exchange) != identity or pillars.evaluated_at != evaluated_at:
        raise ValueError("contribution evidence identity or boundary")
    records: list[MarketAnalysisPillarContributionV1] = []
    candle_source = _candle_source(observation)
    for name in PILLAR_ORDER:
        evidence = pillars.ordered_pillars[name]
        if name in _CANDLE_PILLARS:
            source = candle_source
        else:
            source = _option_source(name, option_chain, contract_ranking)
        status = evidence.status
        available = status == "READY"
        source_contract, source_id, provider_id, source_timestamp = source
        if not available:
            source_contract = source_id = provider_id = source_timestamp = None
        source_missing_warning = () if source_timestamp is not None or not available else ("SOURCE_TIMESTAMP_UNAVAILABLE",)
        records.append(MarketAnalysisPillarContributionV1(
            contribution_id=f"{cycle_id}:{observation_id}:{name}", pillar_name=name,
            underlying_symbol=identity[0], exchange=identity[1], cycle_id=cycle_id, observation_id=observation_id,
            status=status, direction="UNAVAILABLE", raw_score=None, normalized_score=None,
            source_contract_type=source_contract, source_result_id=source_id, source_provider_id=provider_id,
            source_timestamp=source_timestamp, evaluated_at=evaluated_at,
            provenance_classification="GROUPED" if available else "UNAVAILABLE", contribution_available=available,
            blockers=_messages(evidence.summary, "blockers"), warnings=tuple(dict.fromkeys((*_messages(evidence.summary, "warnings"), *source_missing_warning))),
            metadata={"shared_source": True, "independent_direction_available": False, "independent_score_available": False},
        ))
    return MarketAnalysisPillarContributionCollectionV1(cycle_id, observation_id, identity[0], identity[1], evaluated_at, tuple(records))
