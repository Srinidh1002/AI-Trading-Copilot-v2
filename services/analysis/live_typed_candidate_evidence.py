"""Live-boundary assembly of supplied canonical evidence for Task 8.

Provider normalization belongs before this boundary.  Each callable below is
the repository's canonical engine (not a replacement calculation); this
module invokes it once and only packages its typed output for the existing
candidate composer.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from services.analysis.market_analysis_candidate_composer import (
    MarketAnalysisCandidateCompositionInputV1, MarketAnalysisCandidateCompositionPolicyV1,
    _ready,
)
from services.contracts.market_analysis_candidate_v1 import MarketAnalysisEvidenceV1
from services.analysis.live_canonical_evidence_engines import LiveCanonicalEvidenceResultV1


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(name)
    return value


@dataclass(frozen=True, slots=True)
class LiveTypedEvidenceInputV1:
    candidate_id: str; observation_id: str; underlying_symbol: str; exchange: str; option_exchange: str; symboltoken: str
    requested_at: datetime; market_timestamp: datetime; received_at: datetime
    normalized_market: object; normalized_options: object | None
    session: object; direction: str; eligibility: str; confidence: float; score: float
    reasons: tuple[str, ...] = (); invalidation_conditions: tuple[str, ...] = (); blockers: tuple[str, ...] = (); warnings: tuple[str, ...] = (); contradictions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        identity = (self.underlying_symbol.upper(), self.exchange.upper(), self.option_exchange.upper())
        if identity not in {("NIFTY", "NSE", "NFO"), ("SENSEX", "BSE", "BFO")}:
            raise ValueError("unsupported live market identity")
        for name in ("requested_at", "market_timestamp", "received_at"):
            _aware(getattr(self, name), name)
        if self.market_timestamp > self.requested_at or self.requested_at > self.received_at:
            raise ValueError("timestamp ordering")
        if self.normalized_market is None:
            raise ValueError("normalized_market")


@dataclass(frozen=True, slots=True)
class LiveTypedEvidenceEnginesV1:
    freshness: Callable[[LiveTypedEvidenceInputV1], object]
    data_quality: Callable[[LiveTypedEvidenceInputV1], object]
    technical: Callable[[LiveTypedEvidenceInputV1], object]
    multi_timeframe: Callable[[LiveTypedEvidenceInputV1], object]
    regime: Callable[[LiveTypedEvidenceInputV1, object, object], object]
    option_chain: Callable[[LiveTypedEvidenceInputV1], object]
    contract_ranking: Callable[[LiveTypedEvidenceInputV1, object], object]
    pillars: Callable[[LiveTypedEvidenceInputV1, object, object], Mapping[str, MarketAnalysisEvidenceV1]]

    def __post_init__(self) -> None:
        if not all(callable(getattr(self, name)) for name in self.__dataclass_fields__):
            raise TypeError("canonical engines must be callable")


def assemble_live_typed_candidate_evidence(
    source: LiveTypedEvidenceInputV1, engines: LiveTypedEvidenceEnginesV1,
) -> tuple[MarketAnalysisCandidateCompositionInputV1, MarketAnalysisCandidateCompositionPolicyV1]:
    """Call canonical services exactly once and preserve their output verbatim."""
    if type(source) is not LiveTypedEvidenceInputV1 or type(engines) is not LiveTypedEvidenceEnginesV1:
        raise TypeError("exact typed live evidence input and engines required")
    freshness = engines.freshness(source); quality = engines.data_quality(source)
    technical = engines.technical(source); timeframe = engines.multi_timeframe(source)
    regime = engines.regime(source, technical, timeframe)
    option_chain = engines.option_chain(source)
    ranking = engines.contract_ranking(source, option_chain)
    pillars = dict(engines.pillars(source, technical, option_chain))
    required = ("price_action", "candlestick", "chart_pattern", "volume", "volatility", "oi", "oi_change", "pcr", "support_resistance", "max_pain", "iv", "greeks", "premium_behavior", "liquidity_spread")
    if set(pillars) != set(required) or not all(type(pillars[name]) is MarketAnalysisEvidenceV1 for name in required):
        raise ValueError("canonical pillar evidence is incomplete")
    composition = MarketAnalysisCandidateCompositionInputV1(
        candidate_id=source.candidate_id, observation_id=source.observation_id, underlying_symbol=source.underlying_symbol, exchange=source.exchange, option_exchange=source.option_exchange, symboltoken=source.symboltoken,
        requested_at=source.requested_at, market_timestamp=source.market_timestamp, received_at=source.received_at,
        freshness=freshness, data_quality=quality, session=source.session, technical=technical, multi_timeframe=timeframe, regime=regime, option_chain=option_chain, option_contract_eligibility=ranking, broader_market=None, external_context=None,
        evidence_references={"live_boundary": "canonical_engines"}, provenance={"source": "normalized_live_provider"}, **pillars,
    )
    policy = MarketAnalysisCandidateCompositionPolicyV1(direction=source.direction, eligibility=source.eligibility, confidence=source.confidence, score=source.score, blockers=source.blockers, warnings=source.warnings, contradictions=source.contradictions, reasons=source.reasons, invalidation_conditions=source.invalidation_conditions)
    return composition, policy


def compose_from_live_canonical_evidence(*, source: LiveTypedEvidenceInputV1, evidence: LiveCanonicalEvidenceResultV1) -> tuple[MarketAnalysisCandidateCompositionInputV1, MarketAnalysisCandidateCompositionPolicyV1]:
    """Compatibility adapter from the exact 2H aggregate to existing inputs."""
    if type(source) is not LiveTypedEvidenceInputV1 or type(evidence) is not LiveCanonicalEvidenceResultV1: raise TypeError("typed source/evidence")
    if (source.underlying_symbol, source.exchange) != (evidence.observation.spot.underlying_symbol, evidence.observation.spot.exchange): raise ValueError("identity")
    aggregate = evidence.pillars
    candidate_external_context = evidence.external_context if evidence.external_context is None or _ready("external_context", evidence.external_context) else None
    return MarketAnalysisCandidateCompositionInputV1(candidate_id=source.candidate_id, observation_id=source.observation_id, underlying_symbol=source.underlying_symbol, exchange=source.exchange, option_exchange=source.option_exchange, symboltoken=source.symboltoken, requested_at=source.requested_at, market_timestamp=source.market_timestamp, received_at=source.received_at, freshness=evidence.data_quality, data_quality=evidence.data_quality, session=evidence.session, technical=evidence.technical, multi_timeframe=evidence.multi_timeframe, regime=evidence.regime, option_chain=evidence.option_chain, option_contract_eligibility=evidence.contract_ranking, broader_market=evidence.broader_market, external_context=candidate_external_context, evidence_references={"live_boundary":"canonical_evidence"}, provenance={"source":"normalized_live_provider"}, **dict(aggregate.ordered_pillars)), MarketAnalysisCandidateCompositionPolicyV1(direction=source.direction, eligibility=source.eligibility, confidence=source.confidence, score=source.score, blockers=source.blockers + evidence.blockers + aggregate.blockers, warnings=source.warnings + evidence.warnings + aggregate.warnings, contradictions=source.contradictions + evidence.contradictions + aggregate.contradictions, reasons=source.reasons + evidence.reasons + aggregate.reasons, invalidation_conditions=source.invalidation_conditions + evidence.invalidation_conditions + aggregate.invalidation_conditions)
