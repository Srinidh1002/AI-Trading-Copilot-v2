from dataclasses import replace

import pytest

from services.contracts.four_market_ranking_policy_v1 import DEFAULT_FOUR_MARKET_RANKING_POLICY
from services.opportunity_ranking import rank_four_market_opportunities
from tests.fixtures.p5_12 import *


def _candidates():return build_four_market_candidate_set({identity:STRONG_BULLISH for identity in CANONICAL_MARKET_IDENTITIES})
def _identities(result):return tuple((candidate.underlying_symbol,candidate.exchange) for candidate in result.ordered_candidates)


def test_all_equal_and_partial_ties_use_canonical_fallback_independent_of_order():
    candidates=_candidates();first=rank_four_market_opportunities(candidates);reversed_result=rank_four_market_opportunities(tuple(reversed(candidates)))
    assert first.selected_market==CANONICAL_MARKET_IDENTITIES[0] and first.tie_state=='TIE_RESOLVED'
    assert first.tied_markets==CANONICAL_MARKET_IDENTITIES and first.semantic_dict()==reversed_result.semantic_dict()
    partial=list(_candidates());partial[0]=replace(partial[0],opportunity_confidence=.9);partial[1]=replace(partial[1],opportunity_confidence=.9)
    result=rank_four_market_opportunities(tuple(partial));assert result.selected_market==CANONICAL_MARKET_IDENTITIES[0] and CANONICAL_MARKET_IDENTITIES[0] in result.tied_markets


@pytest.mark.parametrize('difference,expect_tie',((0.0,True),(DEFAULT_FOUR_MARKET_RANKING_POLICY.tie_tolerance/2,True),(DEFAULT_FOUR_MARKET_RANKING_POLICY.tie_tolerance*2,False)))
def test_near_tie_boundary_is_deterministic(difference,expect_tie):
    candidates=list(_candidates());candidates[1]=replace(candidates[1],opportunity_confidence=.8+difference)
    result=rank_four_market_opportunities(tuple(reversed(candidates)))
    assert (result.tie_state=='TIE_RESOLVED') is expect_tie
    if not expect_tie:assert result.selected_market==CANONICAL_MARKET_IDENTITIES[1]


def test_tie_ignores_rejected_candidates_and_preserves_slots():
    candidates=list(_candidates());candidates[2]=replace(build_market_opportunity_candidate(CANONICAL_MARKET_IDENTITIES[2],BLOCKED),opportunity_confidence=.99);candidates[3]=build_market_opportunity_candidate(CANONICAL_MARKET_IDENTITIES[3],UNAVAILABLE)
    result=rank_four_market_opportunities(tuple(candidates));reversed_result=rank_four_market_opportunities(tuple(reversed(candidates)))
    assert _identities(result)==CANONICAL_MARKET_IDENTITIES[:2] and result.rank_by_market[CANONICAL_MARKET_IDENTITIES[2]] is None and result.rank_by_market[CANONICAL_MARKET_IDENTITIES[3]] is None
    assert result.tied_markets==CANONICAL_MARKET_IDENTITIES[:2] and result.semantic_dict()==reversed_result.semantic_dict()
