"""Isolated deterministic integration for four supplied market candidates."""
from __future__ import annotations

from services.contracts.four_market_opportunity_ranking_result_v1 import FourMarketOpportunityRankingResultV1
from services.contracts.four_market_ranking_policy_v1 import (
    DEFAULT_FOUR_MARKET_RANKING_POLICY,
    FourMarketRankingPolicyV1,
)
from services.contracts.market_opportunity_candidate_v1 import MarketOpportunityCandidateV1

from .eligibility import evaluate_candidate_eligibility
from .scoring import score_market_opportunity_candidate
from .tie_breaking import resolve_candidate_order


def _unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _market_key(identity: tuple[str, str]) -> str:
    return f"{identity[0]}/{identity[1]}"


def rank_four_market_opportunities(
    candidates: tuple[MarketOpportunityCandidateV1, ...],
    policy: FourMarketRankingPolicyV1 = DEFAULT_FOUR_MARKET_RANKING_POLICY,
) -> FourMarketOpportunityRankingResultV1:
    """Evaluate, score, order, and materialize exactly four supplied candidates."""
    if type(candidates) is not tuple:
        raise TypeError("candidates")
    if type(policy) is not FourMarketRankingPolicyV1:
        raise TypeError("policy")
    if len(candidates) != 4:
        raise ValueError("four candidates required")
    if any(type(candidate) is not MarketOpportunityCandidateV1 for candidate in candidates):
        raise TypeError("candidate")

    candidates_by_identity = {(candidate.underlying_symbol, candidate.exchange): candidate for candidate in candidates}
    if len(candidates_by_identity) != 4 or set(candidates_by_identity) != set(policy.required_market_identities):
        raise ValueError("canonical candidate identities")
    canonical_candidates = tuple(candidates_by_identity[identity] for identity in policy.required_market_identities)
    evaluated_at = canonical_candidates[0].evaluated_at
    if any(candidate.evaluated_at != evaluated_at for candidate in canonical_candidates[1:]):
        raise ValueError("candidate timestamps mismatch")

    eligibility_results = tuple(
        evaluate_candidate_eligibility(candidate, policy)
        for candidate in canonical_candidates
    )
    score_results = tuple(
        score_market_opportunity_candidate(candidate, eligibility, policy)
        for candidate, eligibility in zip(canonical_candidates, eligibility_results)
    )
    tie_result = resolve_candidate_order(
        canonical_candidates, eligibility_results, score_results, policy
    )

    identities = policy.required_market_identities
    eligibility_by_market = {
        identity: eligibility.eligibility_state
        for identity, eligibility in zip(identities, eligibility_results)
    }
    score_by_market = {
        identity: score.final_score
        for identity, score in zip(identities, score_results)
    }
    rank_by_market = {identity: None for identity in identities}
    for rank, candidate in enumerate(tie_result.ordered_candidates, start=1):
        rank_by_market[(candidate.underlying_symbol, candidate.exchange)] = rank

    selected_candidate = tie_result.ordered_candidates[0] if tie_result.selected_market else None
    selected_score = score_by_market[tie_result.selected_market] if tie_result.selected_market else 0.0
    selection_confidence = min(1.0, max(0.0, selected_score))
    blocked = tuple(identity for identity in identities if eligibility_by_market[identity] == "BLOCKED")
    conflicting = tuple(identity for identity in identities if eligibility_by_market[identity] == "CONFLICTING")
    unavailable = tuple(identity for identity in identities if eligibility_by_market[identity] == "UNAVAILABLE")
    warning = tuple(identity for identity in identities if eligibility_by_market[identity] == "ELIGIBLE_WITH_WARNINGS")

    supporting_evidence: list[str] = [f"RANKABLE_MARKET_COUNT:{len(tie_result.ordered_candidates)}"]
    if selected_candidate is not None:
        supporting_evidence.append(
            f"SELECTED_MARKET:{_market_key(tie_result.selected_market)}:FINAL_SCORE:{selected_score}"
        )
    contradictions: list[str] = []
    warnings: list[str] = []
    blockers: list[str] = []
    for identity, candidate, eligibility, score in zip(identities, canonical_candidates, eligibility_results, score_results):
        prefix = _market_key(identity)
        if eligibility.eligibility_state == "CONFLICTING":
            contradictions.extend(f"{prefix}:{reason}" for reason in candidate.contradictions + eligibility.contradictions)
        warnings.extend(f"{prefix}:{reason}" for reason in candidate.warnings + eligibility.warnings + score.warnings)
        if selected_candidate is None and eligibility.eligibility_state in {"BLOCKED", "UNAVAILABLE"}:
            blockers.extend(f"{prefix}:{reason}" for reason in eligibility.blockers)
    warnings.extend(tie_result.warnings)
    if tie_result.tie_state == "TIE_RESOLVED":
        warnings.append("TIE_RESOLVED_BY_CANONICAL_MARKET_ORDER")
    if selected_candidate is None:
        blockers.extend(tie_result.blockers)
        blockers.append("ALL_MARKETS_INELIGIBLE")

    source_timestamps = {
        identity[0]: candidate.evaluated_at
        for identity, candidate in zip(identities, canonical_candidates)
    }
    metadata = {
        "rankable_market_count": len(tie_result.ordered_candidates),
        "selected_market_key": _market_key(tie_result.selected_market) if tie_result.selected_market else None,
        "eligibility_by_market": {_market_key(identity): eligibility_by_market[identity] for identity in identities},
        "score_by_market": {_market_key(identity): score_by_market[identity] for identity in identities},
        "tie_state": tie_result.tie_state,
        "pipeline_version": "P5-11H",
    }
    ranking_result_id = "four-market-ranking:" + ":".join(candidate.candidate_id for candidate in canonical_candidates)
    return FourMarketOpportunityRankingResultV1(
        ranking_result_id,
        evaluated_at,
        canonical_candidates,
        tie_result.ordered_candidates,
        tie_result.selected_market,
        selected_candidate,
        rank_by_market,
        score_by_market,
        eligibility_by_market,
        tie_result.tie_state,
        selection_confidence,
        blocked,
        conflicting,
        unavailable,
        warning,
        tie_result.tied_markets,
        _unique(supporting_evidence),
        _unique(contradictions),
        _unique(blockers) if selected_candidate is None else (),
        _unique(warnings),
        source_timestamps,
        metadata,
    )
