"""Concrete, provider-free bindings for the repository canonical engines."""
from __future__ import annotations

from datetime import datetime

from services.analysis.live_canonical_evidence_engines import LiveCanonicalEvidenceEnginesV1
from services.analysis.market_analysis_candidate_adapters import adapt_technical_pillar_evidence
from services.analysis.market_analysis_option_external_adapters import adapt_option_external_pillar_evidence
from services.analysis.market_analysis_pillar_aggregation import aggregate_market_analysis_pillars, PILLAR_ORDER
from services.contracts.option_contract_ranking_result_v1 import OptionContractRankingResultV1
from services.contracts.market_regime_input_v1 import MarketRegimeInputV1
from services.data_quality.candle_quality import evaluate_market_candle_series_quality
from services.market_regime.service import evaluate_market_regime
from services.market_regime.technical import evaluate_technical_regime_component
from services.market_regime.broader import evaluate_broader_market_regime_component
from services.multi_timeframe.pipeline import build_canonical_multi_timeframe_snapshot
from services.multi_timeframe.quality import evaluate_multi_timeframe_quality
from services.option_chain_intelligence.intelligence_pipeline import build_canonical_option_chain_intelligence, build_unavailable_option_chain_intelligence
from services.option_chain_intelligence.quality import evaluate_option_chain_quality
from services.option_contract_ranking.ranking_pipeline import build_canonical_option_contract_ranking
from services.technical_intelligence.pipeline import build_canonical_technical_intelligence


def _series(observation):
    return tuple(observation.candle_series)


def _data_quality(observation, evaluated_at):
    series = next((item for item in _series(observation) if item.timeframe == "5m"), None)
    if series is None:
        raise ValueError("5m candle series is unavailable")
    return evaluate_market_candle_series_quality(series, clock=lambda: evaluated_at, quality_result_id_factory=lambda: f"live-quality:{series.series_id}")


def _multi_timeframe(observation, quality, evaluated_at):
    snapshot, _ = build_canonical_multi_timeframe_snapshot(
        candle_series_by_timeframe=_series(observation), clock=lambda: evaluated_at,
        snapshot_id_factory=lambda: f"live-mtf:{observation.spot.symboltoken}:{evaluated_at.isoformat()}",
        multi_timeframe_quality_result_id_factory=lambda: f"live-mtf-quality:{observation.spot.symboltoken}:{evaluated_at.isoformat()}",
    )
    return snapshot


def _technical(observation, snapshot, evaluated_at):
    quality = evaluate_multi_timeframe_quality(snapshot, clock=lambda: evaluated_at, quality_result_id_factory=lambda: f"live-mtf-quality:{snapshot.multi_timeframe_snapshot_id}")
    return build_canonical_technical_intelligence(
        candle_series_by_timeframe=_series(observation), multi_timeframe_snapshot=snapshot,
        multi_timeframe_quality_result=quality, clock=lambda: evaluated_at,
        technical_intelligence_result_id_factory=lambda: f"live-technical:{snapshot.multi_timeframe_snapshot_id}",
    )


def _regime(technical, session, evaluated_at, broader_market=None):
    component = evaluate_technical_regime_component(
        underlying_symbol=technical.underlying_symbol, exchange=technical.exchange,
        technical_context=technical, created_at=evaluated_at,
        result_id=f"live-technical-regime:{technical.technical_intelligence_result_id}",
    )
    broader_component = evaluate_broader_market_regime_component(
        underlying_symbol=technical.underlying_symbol, exchange=technical.exchange,
        broader_market_context=broader_market, policy=None, created_at=evaluated_at,
        result_id=f"live-broader-regime:{technical.technical_intelligence_result_id}",
    ) if broader_market is not None else None
    return evaluate_market_regime(MarketRegimeInputV1(
        market_regime_input_id=f"live-regime:{technical.technical_intelligence_result_id}", created_at=evaluated_at,
        underlying_symbol=technical.underlying_symbol, exchange=technical.exchange,
        technical_intelligence=technical, technical_regime_component=component,
        broader_market_intelligence=broader_market, broader_market_regime_component=broader_component,
        market_session_validation=session, source_timestamps={"technical": technical.created_at, "session": session.market_timestamp},
    ))


def _option_chain(options, evaluated_at):
    if options.snapshot is None:
        return build_unavailable_option_chain_intelligence(
            underlying_symbol=options.underlying_symbol,
            exchange=options.exchange, option_exchange=options.option_exchange, evaluated_at=evaluated_at,
            blockers=options.blockers, warnings=options.warnings, reasons=("Captured option chain is unavailable.",),
        )
    quality = evaluate_option_chain_quality(snapshot=options.snapshot, clock=lambda: evaluated_at, option_chain_quality_result_id_factory=lambda: f"live-option-quality:{options.snapshot.option_chain_snapshot_id}")
    return build_canonical_option_chain_intelligence(snapshot=options.snapshot, quality_result=quality, clock=lambda: evaluated_at, option_chain_intelligence_result_id_factory=lambda: f"live-option:{options.snapshot.option_chain_snapshot_id}")


def _contract_ranking(intelligence, options, evaluated_at):
    if options.universe is None:
        return OptionContractRankingResultV1(
            ranking_id=f"live-ranking-unavailable:{intelligence.option_chain_intelligence_result_id}", ranked_at=evaluated_at,
            universe_id=None, intelligence_result_id=intelligence.option_chain_intelligence_result_id,
            underlying_symbol=intelligence.underlying_symbol, exchange=intelligence.exchange,
            directional_bias="UNAVAILABLE", required_option_type=None, ranking_status="INSUFFICIENT_DATA",
            blockers=intelligence.blockers + ("OPTION_CONTRACT_UNIVERSE_UNAVAILABLE",), warnings=intelligence.warnings,
        )
    return build_canonical_option_contract_ranking(intelligence_result=intelligence, universe=options.universe, now=evaluated_at, ranking_id_factory=lambda: f"live-ranking:{options.universe.universe_id}")


def _pillars(observation, option_chain, ranking, evaluated_at):
    candle_ids = tuple(series.series_id for series in observation.candle_series)
    market_ready = bool(candle_ids) and not observation.blockers
    option_ready = option_chain.intelligence_status in {"READY", "READY_WITH_WARNINGS"} and ranking.ranking_status in {"RANKED", "RANKED_WITH_WARNINGS"}
    technical = adapt_technical_pillar_evidence("READY" if market_ready else "UNAVAILABLE", candle_ids if market_ready else (), {"source": "canonical_candle_series"}, {"series_ids": candle_ids} if market_ready else {"blockers": observation.blockers})
    option = adapt_option_external_pillar_evidence("READY" if option_ready else "UNAVAILABLE", (option_chain.option_chain_intelligence_result_id, ranking.ranking_id) if option_ready else (), {"source": "canonical_option_intelligence_and_ranking"}, {"option_chain_intelligence_result_id": option_chain.option_chain_intelligence_result_id, "ranking_id": ranking.ranking_id} if option_ready else {"blockers": option_chain.blockers + ranking.blockers})
    pillars = {name: (technical if name in {"price_action", "candlestick", "chart_pattern", "volume", "volatility"} else option) for name in PILLAR_ORDER}
    return aggregate_market_analysis_pillars(pillars=pillars, evaluated_at=evaluated_at)


def build_default_live_canonical_evidence_engines() -> LiveCanonicalEvidenceEnginesV1:
    return LiveCanonicalEvidenceEnginesV1(_data_quality, _multi_timeframe, _technical, _regime, _option_chain, _contract_ranking, _pillars)
