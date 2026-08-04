"""Provider-free Task 2B shadow ledger.

Only the existing candidate-policy scalar is counted. Technical, option,
regime, ranking, and grouped pillars remain informational to prevent double
counting. Required non-ready evidence and contradictions hard-block exactly as
the existing candidate composer does; no new numerical deduction is invented.
"""
from __future__ import annotations

from services.contracts.market_analysis_confidence_ledger_v1 import MarketAnalysisConfidenceEntryV1, MarketAnalysisConfidenceLedgerV1
from services.contracts.market_analysis_confidence_policy_v1 import MarketAnalysisConfidencePolicyV1


def build_market_analysis_confidence_ledger(*, cycle_id: str, observation_id: str, evidence: object, policy_source: object, confidence_policy: MarketAnalysisConfidencePolicyV1 = MarketAnalysisConfidencePolicyV1()) -> MarketAnalysisConfidenceLedgerV1:
    """Build once from canonical typed evidence; this never changes candidates."""
    from services.analysis.market_analysis_candidate_composer import _ready
    if type(confidence_policy) is not MarketAnalysisConfidencePolicyV1:
        raise TypeError("confidence_policy")
    observation = evidence.observation
    symbol, exchange, when = observation.spot.underlying_symbol, observation.spot.exchange, evidence.pillars.evaluated_at
    required = (("data_quality", evidence.data_quality), ("session", evidence.session), ("technical", evidence.technical), ("multi_timeframe", evidence.multi_timeframe), ("regime", evidence.regime), ("option_chain", evidence.option_chain), ("option_contract_eligibility", evidence.contract_ranking))
    nonready = tuple(name for name, value in required if not _ready(name, value))
    contradictions = tuple(dict.fromkeys((*policy_source.contradictions, *evidence.contradictions, *evidence.pillars.contradictions)))
    hard_block = bool(nonready or contradictions or policy_source.blockers)
    entries: list[MarketAnalysisConfidenceEntryV1] = []
    def controlled_direction(value):
        value = str(value).upper()
        if value in {"BULLISH", "STRONG_BULLISH"}: return "BULLISH"
        if value in {"BEARISH", "STRONG_BEARISH"}: return "BEARISH"
        if value in {"NEUTRAL", "RANGE_BOUND"}: return "NEUTRAL"
        if value == "CONFLICTING": return "CONFLICTING"
        return "UNAVAILABLE"
    def add(entry_type, component, source_id, direction, raw, normalized, counted, reason=None, timestamp=None, blockers=(), warnings=()):
        entries.append(MarketAnalysisConfidenceEntryV1(f"{cycle_id}:{component}", entry_type, component, source_id, None, symbol, exchange, cycle_id, observation_id, direction, raw, normalized, 1.0 if counted else 0.0, raw if counted and raw is not None else 0.0, 0.0, counted, reason, timestamp, when, tuple(blockers), tuple(warnings)))
    add("DIRECTIONAL", "candidate_policy", None, policy_source.direction, policy_source.confidence, policy_source.confidence / 100.0, not hard_block, None if not hard_block else "HARD_BLOCKED", None, policy_source.blockers, policy_source.warnings)
    for component, value, result_id, timestamp in (("technical", evidence.technical, evidence.technical.technical_intelligence_result_id, evidence.technical.created_at), ("option_chain", evidence.option_chain, evidence.option_chain.option_chain_intelligence_result_id, evidence.option_chain.created_at), ("regime", evidence.regime, evidence.regime.market_regime_result_id, evidence.regime.created_at), ("contract_ranking", evidence.contract_ranking, evidence.contract_ranking.ranking_id, evidence.contract_ranking.ranked_at)):
        direction = controlled_direction(getattr(value, "aggregate_bias", getattr(value, "directional_bias", getattr(value, "directional_regime", "UNAVAILABLE"))))
        add("INFORMATIONAL", component, result_id, direction, None, None, False, "ALREADY_ACCOUNTED_FOR", timestamp, getattr(value, "blockers", ()), getattr(value, "warnings", ()))
    for contribution in evidence.contributions.contributions if evidence.contributions is not None else ():
        add("INFORMATIONAL", f"pillar:{contribution.pillar_name}", contribution.source_result_id, contribution.direction, None, None, False, "GROUPED_OR_UNAVAILABLE", contribution.source_timestamp, contribution.blockers, contribution.warnings)
    for code in contradictions:
        add("CONTRADICTION", f"contradiction:{code}", None, "CONFLICTING", None, None, False, "HARD_BLOCKED", None, (code,), ())
    for code in nonready:
        add("QUALITY", f"quality:{code}", None, "UNAVAILABLE", None, None, False, "HARD_BLOCKED", None, (f"EVIDENCE_UNAVAILABLE_{code.upper()}",), ())
    if "session" in nonready or "regime" in nonready:
        add("SUITABILITY", "suitability:session_regime", None, "UNAVAILABLE", None, None, False, "HARD_BLOCKED", None, tuple(f"EVIDENCE_UNAVAILABLE_{name.upper()}" for name in nonready if name in {"session", "regime"}), ())
    final_confidence = 0.0 if hard_block else policy_source.confidence
    final_score = 0.0 if hard_block else policy_source.score
    direction = "CONFLICTING" if contradictions else "UNAVAILABLE" if hard_block else policy_source.direction
    status = "CONFLICTING" if contradictions else "UNAVAILABLE" if hard_block else "READY"
    blockers = tuple(dict.fromkeys((*policy_source.blockers, *(f"EVIDENCE_UNAVAILABLE_{name.upper()}" for name in nonready), *contradictions)))
    return MarketAnalysisConfidenceLedgerV1(f"ledger:{cycle_id}:{observation_id}", symbol, exchange, cycle_id, observation_id, when, policy_source.score, policy_source.confidence, policy_source.confidence if direction == "BULLISH" and not hard_block else 0.0, policy_source.confidence if direction == "BEARISH" and not hard_block else 0.0, policy_source.confidence if direction == "NEUTRAL" and not hard_block else 0.0, 0.0, 0.0, 0.0, final_score, final_confidence, direction, status, tuple(sorted(entries, key=lambda item: item.entry_id)), blockers, tuple(dict.fromkeys((*policy_source.warnings, *evidence.warnings, *evidence.pillars.warnings))), confidence_policy.policy_version)
