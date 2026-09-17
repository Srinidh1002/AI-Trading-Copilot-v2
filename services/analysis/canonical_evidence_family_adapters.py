"""Lossless adapters: canonical intelligence yields one family contribution each."""
from __future__ import annotations
from services.contracts.canonical_evidence_family_v1 import CanonicalEvidenceFamilyContributionV1
from services.contracts.technical_intelligence_result_v1 import TechnicalIntelligenceResultV1
from services.contracts.canonical_market_regime_result_v1 import CanonicalMarketRegimeResultV1
from services.contracts.option_chain_intelligence_result_v1 import OptionChainIntelligenceResultV1
from services.contracts.broader_market_intelligence_result_v1 import BroaderMarketIntelligenceResultV1
from services.contracts.external_market_context_result_v1 import ExternalMarketContextResultV1

def _direction(value: str) -> str: return value if value in {"BULLISH", "BEARISH"} else "UNAVAILABLE" if value == "UNAVAILABLE" else "NEUTRAL"

def technical_family(result: TechnicalIntelligenceResultV1) -> CanonicalEvidenceFamilyContributionV1:
    if type(result) is not TechnicalIntelligenceResultV1: raise TypeError("result")
    ready = result.status in {"READY", "READY_WITH_WARNINGS"}
    return CanonicalEvidenceFamilyContributionV1(family="TECHNICAL", role="DIRECTIONAL", status="AVAILABLE" if ready else "UNAVAILABLE", direction=_direction(result.aggregate_bias) if ready else "UNAVAILABLE", strength=result.aggregate_strength * 100 if ready else 0, quality=100 * result.valid_indicator_count / max(1, result.valid_indicator_count + result.unavailable_indicator_count), observed_at=result.created_at, evidence_ids=(result.technical_intelligence_result_id,), reasons=tuple(result.warnings), diagnostics={"timeframes": result.required_timeframes}, provenance_ids=(result.multi_timeframe_snapshot_id,))

def regime_family(result: CanonicalMarketRegimeResultV1) -> CanonicalEvidenceFamilyContributionV1:
    if type(result) is not CanonicalMarketRegimeResultV1: raise TypeError("result")
    restriction = result.entry_restriction_state not in {"OPEN", "WARNING"} or not result.new_entries_allowed
    return CanonicalEvidenceFamilyContributionV1(family="REGIME", role="ENTRY_RESTRICTION" if restriction else "CONFIRMATION", status="BLOCKED" if restriction else ("AVAILABLE" if result.context_status in {"READY", "READY_WITH_WARNINGS"} else "UNAVAILABLE"), direction="NEUTRAL" if restriction else "NEUTRAL", strength=0, quality=result.confidence * 100, observed_at=result.created_at, evidence_ids=(result.market_regime_result_id,), reasons=tuple(result.blockers if restriction else result.warnings), provenance_ids=tuple(result.supporting_evidence))

def derivatives_family(result: OptionChainIntelligenceResultV1) -> CanonicalEvidenceFamilyContributionV1:
    if type(result) is not OptionChainIntelligenceResultV1: raise TypeError("result")
    ready = result.intelligence_status in {"READY", "READY_WITH_WARNINGS"}
    provenance = (result.option_chain_snapshot_id,) if result.option_chain_snapshot_id else ()
    return CanonicalEvidenceFamilyContributionV1(family="DERIVATIVES", role="DIRECTIONAL", status="AVAILABLE" if ready else "UNAVAILABLE", direction=_direction(result.aggregate_bias) if ready else "UNAVAILABLE", strength=result.aggregate_strength * 100 if ready else 0, quality=100 * result.valid_metric_count / max(1, result.valid_metric_count + result.unavailable_metric_count), observed_at=result.created_at, evidence_ids=(result.option_chain_intelligence_result_id,), reasons=tuple(result.warnings), provenance_ids=provenance)

def broader_market_family(result: BroaderMarketIntelligenceResultV1 | None) -> CanonicalEvidenceFamilyContributionV1:
    """Correlation/VIX context confirms or contradicts; it is never a new vote."""
    if result is None:
        raise ValueError("broader evidence must be explicitly represented by its existing result")
    if type(result) is not BroaderMarketIntelligenceResultV1: raise TypeError("result")
    unavailable = result.intelligence_status in {"UNAVAILABLE", "INSUFFICIENT_DATA", "STALE", "BLOCKED"}
    role = "CONTRADICTION" if result.divergence_state == "DIRECTIONAL_DIVERGENCE" else "CONFIRMATION"
    return CanonicalEvidenceFamilyContributionV1(family="BROADER_MARKET", role=role, status="UNAVAILABLE" if unavailable else "AVAILABLE", direction="UNAVAILABLE" if unavailable else "NEUTRAL", strength=0, quality=result.aggregate_strength * 100 if not unavailable else 0, observed_at=result.created_at, evidence_ids=(result.broader_market_intelligence_result_id,), reasons=tuple(result.blockers if unavailable else result.contradictions if role == "CONTRADICTION" else result.warnings), provenance_ids=tuple(result.supporting_evidence))

def external_context_family(result: ExternalMarketContextResultV1) -> CanonicalEvidenceFamilyContributionV1:
    """Unavailable external domains remain unavailable; only a canonical restriction gates entry."""
    if type(result) is not ExternalMarketContextResultV1: raise TypeError("result")
    # An optional unavailable feed normally reports new_entries_allowed=False;
    # that absence must not masquerade as a valid event/session hard gate.
    hard_restriction = result.entry_restriction_state in {"BLOCKED", "SESSION_OWNED"}
    unavailable = result.context_status == "UNAVAILABLE"
    role = "ENTRY_RESTRICTION" if hard_restriction else "CONTRADICTION" if result.context_status == "CONFLICTING" else "INFORMATIONAL"
    status = "BLOCKED" if hard_restriction else "UNAVAILABLE" if unavailable else "AVAILABLE"
    return CanonicalEvidenceFamilyContributionV1(family="EXTERNAL_CONTEXT", role=role, status=status, direction="NEUTRAL" if status != "UNAVAILABLE" else "UNAVAILABLE", strength=0, quality=result.aggregate_strength * 100 if status == "AVAILABLE" else 0, observed_at=result.created_at, evidence_ids=(result.external_market_context_result_id,), reasons=tuple(result.blockers if hard_restriction else result.contradictions if result.context_status == "CONFLICTING" else result.warnings), provenance_ids=tuple(result.supporting_evidence))
