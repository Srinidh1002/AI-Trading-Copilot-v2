"""Strict bridge from certified live-analysis evidence to a Task 8 candidate.

This is deliberately a conversion boundary, not an intelligence pipeline: it
performs no provider reads, indicator calculation, option-chain construction,
ranking, or execution.  The existing candidate composer remains the only
place that determines candidate eligibility from supplied evidence.
"""
from __future__ import annotations

from collections.abc import Mapping

from services.analysis.market_analysis_candidate_composer import (
    MarketAnalysisCandidateCompositionInputV1,
    MarketAnalysisCandidateCompositionPolicyV1,
    compose_market_analysis_candidate,
)
from services.contracts.market_analysis_candidate_v1 import MarketAnalysisCandidateV1
from services.contracts.paper_orchestration_cycle_input_v1 import PaperOrchestrationCycleInputV1
from services.paper_orchestration.certified_live_read_authorities import CertifiedLiveDataResultV1
from services.contracts.certified_live_captured_evidence_v1 import CertifiedLiveCapturedEvidenceV1
from services.analysis.live_canonical_engine_adapters import build_default_live_canonical_evidence_engines
from services.analysis.live_market_candidate_evaluator import (
    LiveCandidatePolicySourceV1,
    evaluate_captured_certified_market_candidate,
)
from services.contracts.certified_shared_market_context_v1 import CertifiedSharedMarketContextV1


def adapt_task8_live_candidate(
    cycle_input: PaperOrchestrationCycleInputV1,
    data_result: CertifiedLiveDataResultV1,
    supplied_analysis: Mapping[str, object],
    captured_evidence: CertifiedLiveCapturedEvidenceV1 | None = None,
    shared_context: CertifiedSharedMarketContextV1 | None = None,
    *,
    parent_cycle_id: str,
) -> MarketAnalysisCandidateV1:
    """Adapt only exact pre-composed evidence attached by the live reader.

    ``certified_candidate_composition`` and ``certified_candidate_policy``
    are intentionally exact typed objects.  Accepting raw legacy dictionaries
    here would either duplicate intelligence logic or manufacture evidence.
    """
    if type(cycle_input) is not PaperOrchestrationCycleInputV1:
        raise TypeError("cycle_input")
    if type(data_result) is not CertifiedLiveDataResultV1:
        raise TypeError("data_result")
    if not isinstance(supplied_analysis, Mapping):
        raise TypeError("supplied_analysis")
    if captured_evidence is not None and type(captured_evidence) is not CertifiedLiveCapturedEvidenceV1:
        raise TypeError("captured_evidence")
    if shared_context is not None and type(shared_context) is not CertifiedSharedMarketContextV1:
        raise TypeError("shared_context")
    if type(parent_cycle_id) is not str or not parent_cycle_id.strip():
        raise ValueError("parent_cycle_id")
    if shared_context is not None and shared_context.shared_external_context is not None and (shared_context.shared_external_context.cycle_id != shared_context.cycle_id or shared_context.shared_external_context.evaluated_at != shared_context.evaluated_at):
        raise ValueError("shared external context cycle")
    expected = (cycle_input.underlying_symbol, cycle_input.exchange)
    if expected not in {("NIFTY", "NSE"), ("SENSEX", "BSE")}:
        raise ValueError("unsupported Task 8 market")
    if (data_result.underlying_symbol, data_result.exchange) != expected:
        raise ValueError("data identity mismatch")
    composition = supplied_analysis.get("certified_candidate_composition")
    policy = supplied_analysis.get("certified_candidate_policy")
    if captured_evidence is not None and composition is None and policy is None:
        direction = supplied_analysis.get("policy_direction")
        eligibility = supplied_analysis.get("policy_eligibility")
        confidence = supplied_analysis.get("policy_confidence")
        score = supplied_analysis.get("policy_score")
        if all(value is not None for value in (direction, eligibility, confidence, score)):
            source = LiveCandidatePolicySourceV1(
                direction, eligibility, confidence, score,
                tuple(supplied_analysis.get("policy_blockers", ())),
                tuple(supplied_analysis.get("policy_warnings", ())),
                tuple(supplied_analysis.get("policy_contradictions", ())),
                tuple(supplied_analysis.get("policy_reasons", ())),
                tuple(supplied_analysis.get("policy_invalidation_conditions", ())),
            )
        else:
            source = LiveCandidatePolicySourceV1.unavailable()
        return evaluate_captured_certified_market_candidate(
            captured_evidence=captured_evidence,
            session_validation=cycle_input.session_validation,
            policy_source=source,
            parent_cycle_id=parent_cycle_id,
            candidate_id=f"certified-live:{cycle_input.observation_id}",
            observation_id=cycle_input.observation_id,
            engines=build_default_live_canonical_evidence_engines(),
            broader_market=shared_context.for_market(*expected) if shared_context is not None else None,
            external_context=shared_context.shared_external_context.for_market(*expected) if shared_context is not None and shared_context.shared_external_context is not None else None,
        ).candidate
    if type(composition) is not MarketAnalysisCandidateCompositionInputV1:
        raise TypeError("certified_candidate_composition")
    if type(policy) is not MarketAnalysisCandidateCompositionPolicyV1:
        raise TypeError("certified_candidate_policy")
    if (composition.underlying_symbol, composition.exchange) != expected:
        raise ValueError("candidate composition identity mismatch")
    if composition.symboltoken != data_result.symboltoken:
        raise ValueError("candidate composition symboltoken mismatch")
    if composition.observation_id != cycle_input.observation_id:
        raise ValueError("candidate composition observation mismatch")
    if composition.market_timestamp != data_result.market_timestamp:
        raise ValueError("candidate composition timestamp mismatch")
    if composition.requested_at != cycle_input.cycle_requested_at:
        raise ValueError("candidate composition evaluated timestamp mismatch")
    if composition.received_at != cycle_input.received_at:
        raise ValueError("candidate composition receipt timestamp mismatch")
    # The composer independently fail-closes stale/non-ready required evidence,
    # including option-chain and contract/liquidity evidence for eligibility.
    candidate = compose_market_analysis_candidate(composition, policy)
    if type(candidate) is not MarketAnalysisCandidateV1:
        raise TypeError("candidate composer result")
    return candidate
