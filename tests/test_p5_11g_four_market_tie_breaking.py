from services.opportunity_ranking import CandidateEligibilityEvaluationV1, CandidateRankingScoreV1, resolve_candidate_order
from tests.fixtures.p5_10j_market_regime_replay import IDENTITIES
from tests.test_market_opportunity_candidate_v1 import make_candidate


def _eligibility(candidate):
    return CandidateEligibilityEvaluationV1(candidate.underlying_symbol, candidate.exchange, "ELIGIBLE", True)


def _score(candidate):
    return CandidateRankingScoreV1(candidate.underlying_symbol, candidate.exchange, "ELIGIBLE", True, .5, 1.0, .5, .5, {}, (), {}, (), ())


def test_four_equal_markets_use_only_canonical_fallback_independent_of_input_order():
    candidates = tuple(make_candidate(identity) for identity in IDENTITIES)
    forward = resolve_candidate_order(candidates, tuple(_eligibility(candidate) for candidate in candidates), tuple(_score(candidate) for candidate in candidates))
    reverse = resolve_candidate_order(candidates[::-1], tuple(_eligibility(candidate) for candidate in candidates[::-1]), tuple(_score(candidate) for candidate in candidates[::-1]))
    expected = (("NIFTY", "NSE"), ("BANKNIFTY", "NSE"), ("FINNIFTY", "NSE"), ("SENSEX", "BSE"))
    assert forward.tie_state == reverse.tie_state == "TIE_RESOLVED"
    assert forward.ordered_market_identities == reverse.ordered_market_identities == expected
    assert forward.tied_markets == reverse.tied_markets == expected
