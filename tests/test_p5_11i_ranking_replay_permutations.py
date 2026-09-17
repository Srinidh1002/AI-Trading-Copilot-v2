from itertools import permutations

import pytest

from services.opportunity_ranking import rank_four_market_opportunities
from tests.test_p5_11i_ranking_replay_matrix import REPLAY_CASES


_PERMUTATION_CASES = (
    "CLEAR_NIFTY_WINNER", "CLEAR_SENSEX_WINNER", "BLOCKED_HIGH_SCORE_CANNOT_WIN",
    "ALL_INELIGIBLE", "TWO_WAY_CANONICAL_TIE", "FOUR_WAY_CANONICAL_TIE",
    "SCORE_TOLERANCE_ADVANCES_CRITERION", "CONFLICTING_POLICY_ALLOWED",
)


@pytest.mark.parametrize("case_name", _PERMUTATION_CASES)
def test_all_candidate_permutations_match_canonical_replay(case_name):
    case = REPLAY_CASES[case_name]
    baseline = rank_four_market_opportunities(case.candidates, case.policy)
    for ordering in permutations(case.candidates):
        result = rank_four_market_opportunities(ordering, case.policy)
        assert result.semantic_dict() == baseline.semantic_dict(), case_name
        assert result.selected_market == baseline.selected_market
        assert result.rank_by_market == baseline.rank_by_market
        assert result.tie_state == baseline.tie_state and result.tied_markets == baseline.tied_markets
        assert all(any(candidate is original for original in ordering) for candidate in result.candidates)
