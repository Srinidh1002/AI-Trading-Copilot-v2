import pytest

from services.opportunity_ranking import CandidateEligibilityEvaluationV1, score_market_opportunity_candidate
from tests.fixtures.p5_10j_market_regime_replay import IDENTITIES
from tests.test_market_opportunity_candidate_v1 import make_candidate


@pytest.mark.parametrize("identity", IDENTITIES)
def test_equivalent_candidates_score_identically_for_each_canonical_market(identity):
    candidate = make_candidate(identity)
    eligibility = CandidateEligibilityEvaluationV1(
        candidate.underlying_symbol, candidate.exchange, "ELIGIBLE", True
    )
    result = score_market_opportunity_candidate(candidate, eligibility)
    assert result.normalized_base_score == pytest.approx(0.32 / 0.70, abs=1e-12)
    assert result.final_score == pytest.approx(0.32 / 0.70, abs=1e-12)
    assert result.applied_penalties == {}
    assert result.excluded_dimensions[-1] == "EXECUTION_QUALITY"
