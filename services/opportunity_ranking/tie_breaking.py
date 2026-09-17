"""Pure deterministic ordering for already-evaluated market candidates."""
from __future__ import annotations

import functools
import json
from dataclasses import dataclass
from typing import Any

from services.contracts.four_market_ranking_policy_v1 import (
    DEFAULT_FOUR_MARKET_RANKING_POLICY,
    FourMarketRankingPolicyV1,
)
from services.contracts.market_opportunity_candidate_v1 import MarketOpportunityCandidateV1

from .eligibility import CandidateEligibilityEvaluationV1
from .scoring import CandidateRankingScoreV1


_TIE_STATES = {"NO_TIE", "TIE_RESOLVED", "ALL_INELIGIBLE"}
_ELIGIBILITY_PRIORITY = {"ELIGIBLE": 2, "ELIGIBLE_WITH_WARNINGS": 1, "CONFLICTING": 0}


def _unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


@dataclass(frozen=True, slots=True)
class CandidateTieBreakingResultV1:
    """Immutable ordering result for one to four candidate markets."""

    ordered_market_identities: tuple[tuple[str, str], ...]
    ordered_candidates: tuple[MarketOpportunityCandidateV1, ...]
    selected_market: tuple[str, str] | None
    tie_state: str
    tied_markets: tuple[tuple[str, str], ...]
    comparison_trace: tuple[str, ...]
    warnings: tuple[str, ...]
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.tie_state not in _TIE_STATES:
            raise ValueError("tie_state")
        if type(self.ordered_market_identities) is not tuple or type(self.ordered_candidates) is not tuple:
            raise TypeError("ordered values")
        if len(self.ordered_market_identities) != len(self.ordered_candidates):
            raise ValueError("ordered values")
        for identity, candidate in zip(self.ordered_market_identities, self.ordered_candidates):
            if type(identity) is not tuple or len(identity) != 2 or type(candidate) is not MarketOpportunityCandidateV1:
                raise TypeError("ordered candidate")
            if identity != (candidate.underlying_symbol, candidate.exchange):
                raise ValueError("ordered candidate identity")
        if self.selected_market is not None and self.selected_market != self.ordered_market_identities[0]:
            raise ValueError("selected_market")
        if self.tie_state == "ALL_INELIGIBLE" and (self.ordered_candidates or self.selected_market is not None or self.tied_markets):
            raise ValueError("all ineligible")
        for name in ("tied_markets", "comparison_trace", "warnings", "blockers"):
            value = getattr(self, name)
            if type(value) is not tuple:
                raise TypeError(name)

    def to_dict(self) -> dict[str, Any]:
        identity = lambda item: list(item) if item is not None else None
        return {
            "ordered_market_identities": [identity(item) for item in self.ordered_market_identities],
            "ordered_candidates": [candidate.to_dict() for candidate in self.ordered_candidates],
            "selected_market": identity(self.selected_market),
            "tie_state": self.tie_state,
            "tied_markets": [identity(item) for item in self.tied_markets],
            "comparison_trace": list(self.comparison_trace),
            "warnings": list(self.warnings),
            "blockers": list(self.blockers),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)

    def semantic_dict(self) -> dict[str, Any]:
        return self.to_dict()


def _numeric_compare(left: float, right: float, tolerance: float) -> int:
    if abs(left - right) <= tolerance:
        return 0
    return -1 if left > right else 1


def _compare(left: tuple[MarketOpportunityCandidateV1, CandidateEligibilityEvaluationV1, CandidateRankingScoreV1], right: tuple[MarketOpportunityCandidateV1, CandidateEligibilityEvaluationV1, CandidateRankingScoreV1], policy: FourMarketRankingPolicyV1, include_fallback: bool) -> tuple[int, str | None, bool]:
    left_candidate, left_eligibility, left_score = left
    right_candidate, right_eligibility, right_score = right
    deferred_reached = False
    for criterion in policy.tie_breaking_order:
        if criterion == "ELIGIBILITY":
            comparison = _numeric_compare(_ELIGIBILITY_PRIORITY[left_eligibility.eligibility_state], _ELIGIBILITY_PRIORITY[right_eligibility.eligibility_state], 0)
        elif criterion == "FINAL_SCORE":
            comparison = _numeric_compare(left_score.final_score, right_score.final_score, policy.tie_tolerance)
        elif criterion == "OPPORTUNITY_CONFIDENCE":
            comparison = _numeric_compare(left_candidate.opportunity_confidence, right_candidate.opportunity_confidence, policy.tie_tolerance)
        elif criterion == "REGIME_SUITABILITY":
            comparison = _numeric_compare(left_candidate.regime_suitability_score, right_candidate.regime_suitability_score, policy.tie_tolerance)
        elif criterion == "DATA_QUALITY":
            comparison = _numeric_compare(left_candidate.data_quality_score, right_candidate.data_quality_score, policy.tie_tolerance)
        elif criterion == "LIQUIDITY":
            if left_candidate.liquidity_available != right_candidate.liquidity_available:
                comparison = -1 if left_candidate.liquidity_available else 1
            elif not left_candidate.liquidity_available:
                comparison = 0
            else:
                comparison = _numeric_compare(left_candidate.liquidity_score, right_candidate.liquidity_score, policy.tie_tolerance)
        elif criterion == "EXECUTION_QUALITY":
            if left_candidate.execution_quality_available != right_candidate.execution_quality_available:
                comparison = -1 if left_candidate.execution_quality_available else 1
            elif not left_candidate.execution_quality_available:
                comparison = 0
            else:
                comparison = _numeric_compare(left_candidate.execution_quality_score, right_candidate.execution_quality_score, policy.tie_tolerance)
        elif criterion == "FEWER_WARNINGS":
            comparison = _numeric_compare(-len(set(left_candidate.warnings + left_eligibility.warnings + left_score.warnings)), -len(set(right_candidate.warnings + right_eligibility.warnings + right_score.warnings)), 0)
        elif criterion == "FEWER_CONTRADICTIONS":
            comparison = _numeric_compare(-len(set(left_candidate.contradictions + left_eligibility.contradictions)), -len(set(right_candidate.contradictions + right_eligibility.contradictions)), 0)
        elif criterion in {"LOWER_SPREAD", "LOWER_SLIPPAGE"}:
            deferred_reached = True
            comparison = 0
        elif criterion == "CANONICAL_MARKET_ORDER":
            if not include_fallback:
                return 0, None, deferred_reached
            left_order = policy.required_market_identities.index((left_candidate.underlying_symbol, left_candidate.exchange))
            right_order = policy.required_market_identities.index((right_candidate.underlying_symbol, right_candidate.exchange))
            comparison = -1 if left_order < right_order else 1 if left_order > right_order else 0
        else:
            raise ValueError("unsupported tie criterion")
        if comparison:
            return comparison, criterion, deferred_reached
    return 0, None, deferred_reached


def resolve_candidate_order(
    candidates: tuple[MarketOpportunityCandidateV1, ...],
    eligibility_results: tuple[CandidateEligibilityEvaluationV1, ...],
    score_results: tuple[CandidateRankingScoreV1, ...],
    policy: FourMarketRankingPolicyV1 = DEFAULT_FOUR_MARKET_RANKING_POLICY,
) -> CandidateTieBreakingResultV1:
    """Order supplied local outcomes without re-evaluating them."""
    if type(candidates) is not tuple or type(eligibility_results) is not tuple or type(score_results) is not tuple:
        raise TypeError("tuple inputs required")
    if not candidates or len(candidates) != len(eligibility_results) or len(candidates) != len(score_results):
        raise ValueError("input lengths")
    if type(policy) is not FourMarketRankingPolicyV1:
        raise TypeError("policy")

    outcomes: list[tuple[MarketOpportunityCandidateV1, CandidateEligibilityEvaluationV1, CandidateRankingScoreV1]] = []
    identities: set[tuple[str, str]] = set()
    for candidate, eligibility, score in zip(candidates, eligibility_results, score_results):
        if type(candidate) is not MarketOpportunityCandidateV1 or type(eligibility) is not CandidateEligibilityEvaluationV1 or type(score) is not CandidateRankingScoreV1:
            raise TypeError("input item")
        identity = (candidate.underlying_symbol, candidate.exchange)
        if identity not in policy.required_market_identities or identity in identities:
            raise ValueError("candidate identity")
        if identity != (eligibility.underlying_symbol, eligibility.exchange) or identity != (score.underlying_symbol, score.exchange):
            raise ValueError("result identity")
        identities.add(identity)
        outcomes.append((candidate, eligibility, score))

    allowed_states = {"ELIGIBLE", "ELIGIBLE_WITH_WARNINGS"}
    if policy.allow_conflicting_candidate_to_rank:
        allowed_states.add("CONFLICTING")
    rankable = [item for item in outcomes if item[1].rankable and item[2].rankable and item[1].eligibility_state in allowed_states]
    trace = [f"FILTERED_{candidate.underlying_symbol}_{candidate.exchange}" for candidate, eligibility, score in outcomes if (candidate, eligibility, score) not in rankable]
    if not rankable:
        return CandidateTieBreakingResultV1((), (), None, "ALL_INELIGIBLE", (), ("ALL_INELIGIBLE",), (), ("NO_RANKABLE_CANDIDATE",))

    comparator = functools.cmp_to_key(lambda left, right: _compare(left, right, policy, True)[0])
    ordered = sorted(rankable, key=comparator)
    warnings: list[str] = []
    for left, right in zip(ordered, ordered[1:]):
        _, criterion, deferred_reached = _compare(left, right, policy, False)
        if deferred_reached:
            warnings.append("SPREAD_SLIPPAGE_CRITERIA_UNAVAILABLE")
        if criterion is None:
            trace.append("TIE_CRITERIA_EXHAUSTED")
        else:
            trace.append(f"{left[0].underlying_symbol}_{left[0].exchange}_OVER_{right[0].underlying_symbol}_{right[0].exchange}_BY_{criterion}")

    winner = ordered[0]
    ties = [item for item in ordered if _compare(winner, item, policy, False)[0] == 0]
    if len(ties) > 1:
        tie_state = "TIE_RESOLVED"
        tied_markets = tuple((item[0].underlying_symbol, item[0].exchange) for item in ties)
        trace.append("CANONICAL_MARKET_ORDER_FALLBACK")
    else:
        tie_state = "NO_TIE"
        tied_markets = ()
    ordered_candidates = tuple(item[0] for item in ordered)
    ordered_identities = tuple((candidate.underlying_symbol, candidate.exchange) for candidate in ordered_candidates)
    return CandidateTieBreakingResultV1(
        ordered_identities,
        ordered_candidates,
        ordered_identities[0],
        tie_state,
        tied_markets,
        tuple(trace),
        _unique(warnings),
        (),
    )
