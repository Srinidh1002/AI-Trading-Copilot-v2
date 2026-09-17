"""Provider-free compatibility boundary for existing canonical evidence engines."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from inspect import signature

from services.contracts.canonical_market_regime_result_v1 import CanonicalMarketRegimeResultV1
from services.contracts.market_analysis_candidate_v1 import MarketAnalysisEvidenceV1
from services.contracts.market_data_quality_result_v1 import MarketDataQualityResultV1
from services.contracts.market_session_validation_v1 import MarketSessionValidationV1
from services.contracts.multi_timeframe_snapshot_v1 import MultiTimeframeSnapshotV1
from services.contracts.option_chain_intelligence_result_v1 import OptionChainIntelligenceResultV1
from services.contracts.option_contract_ranking_result_v1 import OptionContractRankingResultV1
from services.contracts.technical_intelligence_result_v1 import TechnicalIntelligenceResultV1
from services.contracts.broader_market_intelligence_result_v1 import BroaderMarketIntelligenceResultV1
from services.contracts.external_market_context_result_v1 import ExternalMarketContextResultV1
from services.market.angel_live_observation_normalizer import AngelLiveMarketObservationV1
from services.options.angel_option_chain_normalizer import AngelOptionNormalizationResultV1
from services.analysis.market_analysis_pillar_aggregation import MarketAnalysisPillarAggregationResultV1
from services.analysis.market_analysis_pillar_contributions import build_market_analysis_pillar_contributions
from services.contracts.market_analysis_pillar_contribution_v1 import MarketAnalysisPillarContributionCollectionV1
from services.contracts.market_analysis_confidence_ledger_v1 import MarketAnalysisConfidenceLedgerV1


_PILLARS = ("price_action", "candlestick", "chart_pattern", "volume", "volatility", "oi", "oi_change", "pcr", "support_resistance", "max_pain", "iv", "greeks", "premium_behavior", "liquidity_spread")


def _aware(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None: raise ValueError("evaluated_at")
    return value

@dataclass(frozen=True, slots=True)
class LiveCanonicalEvidenceEnginesV1:
    data_quality: Callable[[AngelLiveMarketObservationV1, datetime], MarketDataQualityResultV1]
    multi_timeframe: Callable[[AngelLiveMarketObservationV1, MarketDataQualityResultV1, datetime], MultiTimeframeSnapshotV1]
    technical: Callable[[AngelLiveMarketObservationV1, MultiTimeframeSnapshotV1, datetime], TechnicalIntelligenceResultV1]
    regime: Callable[..., CanonicalMarketRegimeResultV1]
    option_chain: Callable[[AngelOptionNormalizationResultV1, datetime], OptionChainIntelligenceResultV1]
    contract_ranking: Callable[[OptionChainIntelligenceResultV1, AngelOptionNormalizationResultV1, datetime], OptionContractRankingResultV1]
    pillars: Callable[[AngelLiveMarketObservationV1, OptionChainIntelligenceResultV1, OptionContractRankingResultV1, datetime], MarketAnalysisPillarAggregationResultV1]

    def __post_init__(self) -> None:
        if not all(callable(getattr(self, name)) for name in self.__dataclass_fields__): raise TypeError("canonical engine callable")

@dataclass(frozen=True, slots=True)
class LiveCanonicalEvidenceResultV1:
    observation: AngelLiveMarketObservationV1
    session: MarketSessionValidationV1
    data_quality: MarketDataQualityResultV1
    multi_timeframe: MultiTimeframeSnapshotV1
    technical: TechnicalIntelligenceResultV1
    broader_market: BroaderMarketIntelligenceResultV1 | None
    external_context: ExternalMarketContextResultV1 | None
    regime: CanonicalMarketRegimeResultV1
    option_chain: OptionChainIntelligenceResultV1
    contract_ranking: OptionContractRankingResultV1
    pillars: MarketAnalysisPillarAggregationResultV1
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()
    contributions: MarketAnalysisPillarContributionCollectionV1 | None = None
    confidence_ledger: MarketAnalysisConfidenceLedgerV1 | None = None

    def __post_init__(self) -> None:
        if type(self.observation) is not AngelLiveMarketObservationV1 or type(self.session) is not MarketSessionValidationV1: raise TypeError("observation/session")
        required = (MarketDataQualityResultV1, MultiTimeframeSnapshotV1, TechnicalIntelligenceResultV1, CanonicalMarketRegimeResultV1, OptionChainIntelligenceResultV1, OptionContractRankingResultV1)
        if any(type(value) is not expected for value, expected in zip((self.data_quality,self.multi_timeframe,self.technical,self.regime,self.option_chain,self.contract_ranking), required)): raise TypeError("canonical evidence")
        identity = (self.observation.spot.underlying_symbol, self.observation.spot.exchange)
        if any((getattr(item,"underlying_symbol"),getattr(item,"exchange")) != identity for item in (self.data_quality,self.multi_timeframe,self.technical,self.regime,self.option_chain,self.contract_ranking)): raise ValueError("canonical evidence identity")
        if type(self.pillars) is not MarketAnalysisPillarAggregationResultV1: raise TypeError("pillar aggregation")
        if self.contributions is not None and (type(self.contributions) is not MarketAnalysisPillarContributionCollectionV1 or (self.contributions.underlying_symbol, self.contributions.exchange) != identity or self.contributions.evaluated_at != self.pillars.evaluated_at): raise ValueError("pillar contribution coherence")
        if self.confidence_ledger is not None and (type(self.confidence_ledger) is not MarketAnalysisConfidenceLedgerV1 or (self.confidence_ledger.underlying_symbol, self.confidence_ledger.exchange) != identity or self.confidence_ledger.evaluated_at != self.pillars.evaluated_at): raise ValueError("confidence ledger coherence")
        if self.broader_market is not None and (type(self.broader_market) is not BroaderMarketIntelligenceResultV1 or (self.broader_market.underlying_symbol, self.broader_market.exchange) != identity): raise ValueError("broader market identity")
        if self.external_context is not None and (type(self.external_context) is not ExternalMarketContextResultV1 or (self.external_context.underlying_symbol, self.external_context.exchange) != identity or self.external_context.created_at != self.regime.created_at): raise ValueError("external context identity or evaluation boundary")
        for name in ("blockers","warnings","contradictions","reasons","invalidation_conditions"):
            if not isinstance(getattr(self,name),tuple): raise TypeError(name)

def build_live_canonical_evidence(*, observation: AngelLiveMarketObservationV1, options: AngelOptionNormalizationResultV1, session: MarketSessionValidationV1, evaluated_at: datetime, engines: LiveCanonicalEvidenceEnginesV1, cycle_id: str | None = None, observation_id: str | None = None, broader_market: BroaderMarketIntelligenceResultV1 | None = None, external_context: ExternalMarketContextResultV1 | None = None, blockers: tuple[str,...]=(), warnings: tuple[str,...]=(), contradictions: tuple[str,...]=(), reasons: tuple[str,...]=(), invalidation_conditions: tuple[str,...]=()) -> LiveCanonicalEvidenceResultV1:
    """Call each supplied canonical service once in dependency order."""
    if type(observation) is not AngelLiveMarketObservationV1 or type(options) is not AngelOptionNormalizationResultV1 or type(session) is not MarketSessionValidationV1 or type(engines) is not LiveCanonicalEvidenceEnginesV1: raise TypeError("exact typed inputs")
    _aware(evaluated_at)
    identity = (observation.spot.underlying_symbol, observation.spot.exchange)
    if (session.symbol, session.exchange) != identity: raise ValueError("session identity")
    quality = engines.data_quality(observation, evaluated_at)
    timeframe = engines.multi_timeframe(observation, quality, evaluated_at)
    technical = engines.technical(observation, timeframe, evaluated_at)
    try:
        signature(engines.regime).bind(technical, session, evaluated_at, broader_market, external_context)
    except TypeError:
        try:
            signature(engines.regime).bind(technical, session, evaluated_at, broader_market)
        except TypeError:
            regime = engines.regime(technical, session, evaluated_at)
        else:
            regime = engines.regime(technical, session, evaluated_at, broader_market)
    else:
        regime = engines.regime(technical, session, evaluated_at, broader_market, external_context)
    option_chain = engines.option_chain(options, evaluated_at)
    ranking = engines.contract_ranking(option_chain, options, evaluated_at)
    pillars = engines.pillars(observation, option_chain, ranking, evaluated_at)
    contributions = None
    if cycle_id is not None or observation_id is not None:
        if not isinstance(cycle_id, str) or not isinstance(observation_id, str): raise ValueError("cycle and observation identifiers are required together")
        contributions = build_market_analysis_pillar_contributions(cycle_id=cycle_id, observation_id=observation_id, observation=observation, option_chain=option_chain, contract_ranking=ranking, pillars=pillars, evaluated_at=evaluated_at)
    return LiveCanonicalEvidenceResultV1(observation, session, quality, timeframe, technical, broader_market, external_context, regime, option_chain, ranking, pillars, blockers, warnings, contradictions, reasons, invalidation_conditions, contributions)
