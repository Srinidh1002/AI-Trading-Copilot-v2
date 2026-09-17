from dataclasses import replace

import pytest

from services.contracts.four_market_ranking_policy_v1 import FourMarketRankingPolicyV1
from services.opportunity_ranking import (
    CandidateEligibilityEvaluationV1,
    CandidateRankingScoreV1,
    score_market_opportunity_candidate,
)
from tests.test_market_opportunity_candidate_v1 import make_candidate


def eligible(candidate, **changes):
    values = dict(
        underlying_symbol=candidate.underlying_symbol,
        exchange=candidate.exchange,
        eligibility_state="ELIGIBLE",
        rankable=True,
    )
    values.update(changes)
    return CandidateEligibilityEvaluationV1(**values)


def test_public_api_exact_types_identity_and_immutable_result():
    candidate = make_candidate()
    evaluation = eligible(candidate)
    result = score_market_opportunity_candidate(candidate, evaluation)
    assert type(result) is CandidateRankingScoreV1
    with pytest.raises(TypeError):
        score_market_opportunity_candidate({}, evaluation)
    with pytest.raises(TypeError):
        score_market_opportunity_candidate(candidate, {})
    with pytest.raises(TypeError):
        score_market_opportunity_candidate(candidate, evaluation, {})
    with pytest.raises(ValueError):
        score_market_opportunity_candidate(candidate, replace(evaluation, underlying_symbol="BANKNIFTY"))
    with pytest.raises(Exception):
        result.final_score = 0.0
    with pytest.raises(TypeError):
        result.applied_penalties["X"] = 1.0


def test_weighted_score_optional_exclusion_and_deterministic_serialization():
    candidate = make_candidate()
    result = score_market_opportunity_candidate(candidate, eligible(candidate))
    assert result.excluded_dimensions == (
        "OPTION_CHAIN_CONFIRMATION", "BROADER_MARKET_CONFIRMATION",
        "EXTERNAL_CONTEXT_CONFIRMATION", "LIQUIDITY", "EXECUTION_QUALITY",
    )
    assert result.raw_weighted_score == pytest.approx(0.32, abs=1e-12)
    assert result.usable_weight_sum == pytest.approx(0.70, abs=1e-12)
    assert result.normalized_base_score == pytest.approx(0.32 / 0.70, abs=1e-12)
    assert result.final_score == pytest.approx(result.normalized_base_score, abs=1e-12)
    assert tuple(result.component_contributions) == (
        "OPPORTUNITY_CONFIDENCE", "REGIME_SUITABILITY", "TECHNICAL_CONFIRMATION",
        "OPTION_CHAIN_CONFIRMATION", "BROADER_MARKET_CONFIRMATION",
        "EXTERNAL_CONTEXT_CONFIRMATION", "DATA_QUALITY", "LIQUIDITY", "EXECUTION_QUALITY",
    )
    assert result.to_dict() == result.to_dict()
    assert result.to_json() == result.to_json()
    assert result.semantic_dict() == result.semantic_dict()


def test_disabled_exclusion_uses_zero_optional_values_and_configured_weights():
    candidate = make_candidate()
    policy = FourMarketRankingPolicyV1(exclude_unavailable_optional_scores_from_denominator=False)
    result = score_market_opportunity_candidate(candidate, eligible(candidate), policy)
    assert result.excluded_dimensions == ()
    assert result.usable_weight_sum == pytest.approx(sum(policy.ranking_weights.values()), abs=1e-12)
    assert result.component_contributions["OPTION_CHAIN_CONFIRMATION"]["usable"] is True
    assert result.component_contributions["OPTION_CHAIN_CONFIRMATION"]["weighted_contribution"] == 0.0


def test_penalties_are_once_only_and_nonrankable_scores_fail_closed():
    candidate = make_candidate(candidate_status="READY_WITH_WARNINGS", warnings=("ONE", "TWO"))
    evaluation = eligible(
        candidate,
        eligibility_state="ELIGIBLE_WITH_WARNINGS",
        warnings=("ONE", "TWO"),
        missing_optional_references=("OPTION_CHAIN", "LIQUIDITY"),
        freshness_failure="MIXED",
        spread_limit_breach=True,
        slippage_limit_breach=True,
    )
    result = score_market_opportunity_candidate(candidate, evaluation)
    assert tuple(result.applied_penalties) == (
        "WARNING", "MISSING_OPTIONAL_EVIDENCE", "STALE_DATA", "SPREAD", "SLIPPAGE",
    )
    assert result.applied_penalties["WARNING"] == 0.05
    assert result.final_score == pytest.approx(0.4571428571428572 - 0.30, abs=1e-12)
    blocked = score_market_opportunity_candidate(candidate, eligible(candidate, eligibility_state="BLOCKED", rankable=False, blockers=("BLOCK",)))
    assert blocked.final_score == 0.0
    assert blocked.rankable is False


def test_non_unit_weights_and_no_usable_denominator_are_safe():
    candidate = make_candidate()
    high_weight_policy = FourMarketRankingPolicyV1(
        opportunity_confidence_weight=2, regime_suitability_weight=1,
        technical_confirmation_weight=1, option_chain_confirmation_weight=0,
        broader_market_confirmation_weight=0, external_context_confirmation_weight=0,
        data_quality_weight=1, liquidity_weight=0, execution_quality_weight=0,
    )
    high = score_market_opportunity_candidate(candidate, eligible(candidate), high_weight_policy)
    assert high.usable_weight_sum == 5.0
    assert high.normalized_base_score == pytest.approx(0.48, abs=1e-12)
    zero_basis_policy = FourMarketRankingPolicyV1(
        opportunity_confidence_weight=0, regime_suitability_weight=0,
        technical_confirmation_weight=0, option_chain_confirmation_weight=1,
        broader_market_confirmation_weight=0, external_context_confirmation_weight=0,
        data_quality_weight=0, liquidity_weight=0, execution_quality_weight=0,
    )
    no_basis = score_market_opportunity_candidate(candidate, eligible(candidate), zero_basis_policy)
    assert no_basis.final_score == 0.0
    assert no_basis.rankable is False
    assert "NO_USABLE_SCORE_WEIGHT" in no_basis.blockers
