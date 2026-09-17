from dataclasses import replace
from datetime import timedelta
import json

from services.contracts.four_market_ranking_policy_v1 import DEFAULT_FOUR_MARKET_RANKING_POLICY
from services.opportunity_ranking import evaluate_candidate_eligibility, rank_four_market_opportunities, score_market_opportunity_candidate
from tests.fixtures.p5_12 import *


def test_fixture_boundary_classification_is_deterministic_and_not_production_age_calculation():
    timestamps = dict(build_freshness_timestamp_profile('FRESH'))
    timestamps['technical'] = REPLAY_EVALUATED_AT - timedelta(seconds=300)
    timestamps['market_regime'] = REPLAY_EVALUATED_AT + timedelta(seconds=5)
    exact = classify_fixture_freshness_profile(timestamps)
    assert exact.classifications['technical'] == 'DELAYED'
    assert exact.classifications['market_regime'] == 'FRESH'
    timestamps['technical'] -= timedelta(seconds=1)
    timestamps['market_regime'] += timedelta(seconds=1)
    beyond = classify_fixture_freshness_profile(timestamps)
    assert beyond.classifications['technical'] == 'STALE' and beyond.classifications['market_regime'] == 'FUTURE'
    skew = dict(build_freshness_timestamp_profile('FRESH'))
    skew['broader_market'] = REPLAY_EVALUATED_AT - timedelta(seconds=900)
    assert classify_fixture_freshness_profile(skew).skew_diagnostic == 'NONE'
    skew['broader_market'] -= timedelta(seconds=1)
    assert classify_fixture_freshness_profile(skew).skew_diagnostic == 'SKEW'


def test_penalties_are_applied_once_and_default_denominator_excludes_missing_optionals():
    identity = CANONICAL_MARKET_IDENTITIES[0]
    states = {'option_chain': 'MISSING_OPTIONAL', 'broader_market': 'MISSING_OPTIONAL', 'external_context': 'MISSING_OPTIONAL', 'liquidity': 'MISSING_OPTIONAL'}
    candidate = build_market_opportunity_candidate(identity, STRONG_BULLISH, optional_component_states=states)
    eligibility = evaluate_candidate_eligibility(candidate)
    score = score_market_opportunity_candidate(candidate, eligibility)
    assert list(score.applied_penalties).count('WARNING') == 1
    assert list(score.applied_penalties).count('MISSING_OPTIONAL_EVIDENCE') == 1
    assert {'OPTION_CHAIN_CONFIRMATION', 'BROADER_MARKET_CONFIRMATION', 'EXTERNAL_CONTEXT_CONFIRMATION', 'LIQUIDITY'} <= set(score.excluded_dimensions)
    compatibility = replace(DEFAULT_FOUR_MARKET_RANKING_POLICY, exclude_unavailable_optional_scores_from_denominator=False)
    compatibility_score = score_market_opportunity_candidate(candidate, eligibility, compatibility)
    assert not compatibility_score.excluded_dimensions
    assert compatibility_score.usable_weight_sum > score.usable_weight_sum
    assert 0.0 <= compatibility_score.final_score <= 1.0


def test_serialization_order_independence_and_no_mutation():
    profiles = {identity: build_freshness_timestamp_profile('FRESH') for identity in CANONICAL_MARKET_IDENTITIES}
    before = {identity: dict(profile) for identity, profile in profiles.items()}
    matrix = {identity: STRONG_BULLISH for identity in CANONICAL_MARKET_IDENTITIES}
    first = build_ranked_four_market_result(matrix, source_timestamps_by_market=profiles)
    second = build_ranked_four_market_result(matrix, source_timestamps_by_market=profiles)
    assert first.to_dict() == second.to_dict() and first.to_json() == second.to_json() and first.semantic_dict() == second.semantic_dict()
    assert before == {identity: dict(profile) for identity, profile in profiles.items()}
    payload = first.to_dict(); payload['metadata']['changed'] = True
    assert 'changed' not in first.metadata and json.loads(first.to_json())['execution_mode'] == 'PAPER'
    reversed_result = rank_four_market_opportunities(tuple(reversed(build_four_market_candidate_set(matrix))))
    assert reversed_result.semantic_dict() == first.semantic_dict()


def test_missing_required_evaluator_case_is_safe_and_provider_payload_free():
    case = build_missing_required_evaluation_case(CANONICAL_MARKET_IDENTITIES[0], STRONG_BULLISH)
    assert type(case.baseline_candidate).__name__ == 'MarketOpportunityCandidateV1'
    assert case.missing_component == 'MARKET_REGIME'
    assert case.evaluator_result_kwargs()['missing_required_reference'] is True
    optional = build_market_opportunity_candidate(CANONICAL_MARKET_IDENTITIES[0], STRONG_BULLISH, component_quality_profile=OPTIONAL_PROVIDER_BLOCKED_PROFILE)
    assert optional.candidate_status == 'READY_WITH_WARNINGS' and optional.blockers == ()
    assert 'raw_payload' not in json.dumps(optional.to_dict()).lower()
