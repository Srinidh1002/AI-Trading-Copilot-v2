from dataclasses import replace

import pytest

from services.contracts.four_market_ranking_policy_v1 import FourMarketRankingPolicyV1
from services.opportunity_ranking import (
    CandidateEligibilityEvaluationV1,
    CandidateRankingScoreV1,
    CandidateTieBreakingResultV1,
    resolve_candidate_order,
)
from tests.test_market_opportunity_candidate_v1 import make_candidate


def eligibility(candidate, state="ELIGIBLE", rankable=True, **changes):
    values = dict(underlying_symbol=candidate.underlying_symbol, exchange=candidate.exchange, eligibility_state=state, rankable=rankable)
    values.update(changes)
    return CandidateEligibilityEvaluationV1(**values)


def score(candidate, final_score=.5, rankable=True, **changes):
    values = dict(
        underlying_symbol=candidate.underlying_symbol, exchange=candidate.exchange,
        eligibility_state="ELIGIBLE", rankable=rankable, raw_weighted_score=final_score,
        usable_weight_sum=1.0, normalized_base_score=final_score, final_score=final_score,
        applied_penalties={}, excluded_dimensions=(), component_contributions={}, warnings=(), blockers=(),
    )
    values.update(changes)
    return CandidateRankingScoreV1(**values)


def test_public_api_validates_exact_tuples_items_lengths_and_identity():
    candidate = make_candidate()
    evaluation, result = eligibility(candidate), score(candidate)
    ordered = resolve_candidate_order((candidate,), (evaluation,), (result,))
    assert type(ordered) is CandidateTieBreakingResultV1
    with pytest.raises(TypeError):
        resolve_candidate_order([candidate], (evaluation,), (result,))
    with pytest.raises(TypeError):
        resolve_candidate_order((object(),), (evaluation,), (result,))
    with pytest.raises(ValueError):
        resolve_candidate_order((), (), ())
    with pytest.raises(ValueError):
        resolve_candidate_order((candidate,), (), (result,))
    with pytest.raises(ValueError):
        resolve_candidate_order((candidate, candidate), (evaluation, evaluation), (result, result))
    with pytest.raises(ValueError):
        resolve_candidate_order((candidate,), (replace(evaluation, exchange="BSE"),), (result,))


def test_filtering_and_all_ineligible_fail_closed():
    candidate = make_candidate()
    blocked = resolve_candidate_order((candidate,), (eligibility(candidate, "BLOCKED", False),), (score(candidate, rankable=False),))
    assert blocked.tie_state == "ALL_INELIGIBLE"
    assert blocked.selected_market is None and blocked.blockers
    conflicting = resolve_candidate_order((candidate,), (eligibility(candidate, "CONFLICTING", True),), (score(candidate),))
    assert conflicting.tie_state == "ALL_INELIGIBLE"
    policy = FourMarketRankingPolicyV1(allow_conflicting_candidate_to_rank=True)
    allowed = resolve_candidate_order((candidate,), (eligibility(candidate, "CONFLICTING", True),), (score(candidate),), policy)
    assert allowed.selected_market == ("NIFTY", "NSE")
    zero = resolve_candidate_order((candidate,), (eligibility(candidate),), (score(candidate, 0.0),))
    assert zero.selected_market == ("NIFTY", "NSE")


def test_eligible_ranks_above_eligible_with_warnings_before_score():
    nifty, bank = make_candidate(("NIFTY", "NSE")), make_candidate(("BANKNIFTY", "NSE"))
    result = resolve_candidate_order((bank, nifty), (eligibility(bank), eligibility(nifty, "ELIGIBLE_WITH_WARNINGS")), (score(bank, .9), score(nifty, .1)))
    assert result.ordered_candidates[0] is bank
    assert result.selected_market == ("BANKNIFTY", "NSE")
    assert result.ordered_candidates == (bank, nifty)
    assert result.ordered_market_identities == (("BANKNIFTY", "NSE"), ("NIFTY", "NSE"))


def test_final_score_orders_candidates_with_equal_eligibility():
    nifty, bank = make_candidate(("NIFTY", "NSE")), make_candidate(("BANKNIFTY", "NSE"))
    result = resolve_candidate_order((nifty, bank), (eligibility(nifty), eligibility(bank)), (score(nifty, .1), score(bank, .9)))
    assert result.ordered_candidates == (bank, nifty)
    assert "BANKNIFTY_NSE_OVER_NIFTY_NSE_BY_FINAL_SCORE" in result.comparison_trace


def test_scores_within_tolerance_use_next_criterion_and_not_input_order():
    nifty, bank = make_candidate(("NIFTY", "NSE")), make_candidate(("BANKNIFTY", "NSE"))
    scores = resolve_candidate_order((nifty, bank), (eligibility(nifty), eligibility(bank)), (score(nifty, .5), score(bank, .5000000000005)))
    assert scores.tie_state == "TIE_RESOLVED"
    assert scores.selected_market == ("NIFTY", "NSE")
    assert scores.tied_markets == (("NIFTY", "NSE"), ("BANKNIFTY", "NSE"))
    assert "CANONICAL_MARKET_ORDER_FALLBACK" in scores.comparison_trace
    reversed_scores = resolve_candidate_order((bank, nifty), (eligibility(bank), eligibility(nifty)), (score(bank, .5000000000005), score(nifty, .5)))
    assert reversed_scores.ordered_market_identities == scores.ordered_market_identities


def test_output_preserves_original_objects_and_is_deterministically_serialized():
    nifty, bank = make_candidate(("NIFTY", "NSE")), make_candidate(("BANKNIFTY", "NSE"))
    result = resolve_candidate_order((bank, nifty), (eligibility(bank), eligibility(nifty)), (score(bank, .6), score(nifty, .4)))
    assert result.ordered_candidates == (bank, nifty)
    assert result.ordered_market_identities == (("BANKNIFTY", "NSE"), ("NIFTY", "NSE"))
    assert result.to_dict() == result.to_dict()
    assert result.to_json() == result.to_json()
    assert result.semantic_dict() == result.semantic_dict()
    with pytest.raises(Exception):
        result.selected_market = None
