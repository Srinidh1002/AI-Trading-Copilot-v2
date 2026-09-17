"""P5-12F deterministic replay certification for repeated typed builds."""
from __future__ import annotations

import json

import pytest

from services.opportunity_ranking import evaluate_candidate_eligibility, rank_four_market_opportunities, score_market_opportunity_candidate
from tests.fixtures.p5_12 import *


_SCENARIOS = (STRONG_BULLISH, STRONG_BEARISH, WEAK_BULLISH, RANGE_BOUND, HIGH_VOLATILITY, CONFLICTING, BLOCKED, UNAVAILABLE, FRESH, DELAYED, STALE, FUTURE, MIXED_TIMESTAMPS, PARTIAL_OPTIONAL, PROVIDER_BLOCKED, RBI_BLOCK, CPI_WARNING, HOLIDAY, SPECIAL_SESSION, WEEKLY_EXPIRY, MONTHLY_EXPIRY, ROLLOVER, OVERLAPPING_EVENTS, EVENT_PLUS_SESSION_RESTRICTION)


def _event_profile(scenario):
    return {RBI_BLOCK: RBI_BLOCK_EVENT_PROFILE, CPI_WARNING: CPI_WARNING_EVENT_PROFILE, WEEKLY_EXPIRY: WEEKLY_EXPIRY_EVENT_PROFILE, MONTHLY_EXPIRY: MONTHLY_EXPIRY_EVENT_PROFILE, ROLLOVER: ROLLOVER_EVENT_PROFILE, OVERLAPPING_EVENTS: OVERLAPPING_EVENTS_PROFILE, EVENT_PLUS_SESSION_RESTRICTION: CPI_WARNING_EVENT_PROFILE}.get(scenario)


def _session_profile(scenario):
    return {HOLIDAY: HOLIDAY_SESSION, SPECIAL_SESSION: SPECIAL_SESSION_PROFILE, EVENT_PLUS_SESSION_RESTRICTION: HOLIDAY_SESSION}.get(scenario)


def _source_timestamp_kwargs(timestamps, component):
    return {"source_timestamp": timestamps[component]} if component in timestamps else {}


def _json_safe_representation(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _assert_repeated_serialization_equal(left, right):
    assert left == right
    to_dict = getattr(left, "to_dict", None)
    if callable(to_dict):
        left_dict, right_dict = left.to_dict(), right.to_dict()
        assert left_dict == right_dict
        assert _json_safe_representation(left_dict) == _json_safe_representation(right_dict)
    to_json = getattr(left, "to_json", None)
    if callable(to_json):
        assert left.to_json() == right.to_json()
    semantic_dict = getattr(left, "semantic_dict", None)
    if callable(semantic_dict):
        assert semantic_dict() == right.semantic_dict()


def _layers(identity, scenario):
    event_profile = _event_profile(scenario); session_profile = _session_profile(scenario)
    freshness = "MIXED" if scenario is MIXED_TIMESTAMPS else scenario.freshness_state if scenario.freshness_state in {"FRESH", "DELAYED", "STALE", "FUTURE", "UNAVAILABLE"} else "FRESH"
    timestamps = build_freshness_timestamp_profile(freshness)
    technical = build_technical_intelligence(identity, scenario, **_source_timestamp_kwargs(timestamps, "technical"))
    option_chain = build_option_chain_intelligence(identity, scenario, **_source_timestamp_kwargs(timestamps, "option_chain"))
    broader = build_broader_market_intelligence(identity, scenario, **_source_timestamp_kwargs(timestamps, "broader_market"))
    external = build_external_context(identity, scenario, event_profile=event_profile, **_source_timestamp_kwargs(timestamps, "external_context"))
    session = build_market_session_validation(identity, session_profile=session_profile or REGULAR_SESSION)
    event = build_event_risk_context(identity, event_profile=event_profile or NONE)
    regime = build_market_regime(identity, scenario, source_timestamps=timestamps, event_profile=event_profile, session_profile=session_profile, market_session_validation=session)
    opportunity = build_trade_opportunity(identity, scenario, market_regime=regime, option_chain=option_chain, **_source_timestamp_kwargs(timestamps, "trade_opportunity"))
    candidate = build_market_opportunity_candidate(identity, scenario, source_timestamps=timestamps, event_profile=event_profile, session_profile=session_profile)
    eligibility = evaluate_candidate_eligibility(candidate)
    score = score_market_opportunity_candidate(candidate, eligibility)
    return technical, option_chain, broader, external, event, session, regime, opportunity, candidate, eligibility, score


@pytest.mark.parametrize("scenario", _SCENARIOS, ids=lambda value: value.scenario_name)
@pytest.mark.parametrize("identity", CANONICAL_MARKET_IDENTITIES)
def test_repeated_full_stack_layers_are_exactly_equal(identity, scenario):
    first = _layers(identity, scenario); second = _layers(identity, scenario)
    assert first == second
    for left, right in zip(first, second, strict=True):
        assert type(left) is type(right)
        _assert_repeated_serialization_equal(left, right)
    candidate = first[-3]
    eligibility = first[-2]
    score = first[-1]
    assert candidate.evaluated_at == REPLAY_EVALUATED_AT
    assert all(timestamp.tzinfo is not None for timestamp in candidate.source_timestamps.values())
    assert candidate.execution_mode == "PAPER" and candidate.live_execution_eligible is False
    if scenario is UNAVAILABLE:
        assert dict(candidate.source_timestamps) == {}
        assert candidate.candidate_status == "UNAVAILABLE"
        assert candidate.trade_opportunity is None and candidate.option_chain_available is False
        assert candidate.broader_market_intelligence is None and candidate.external_market_context is None
        assert eligibility.rankable is False and score.final_score == 0.0
        assert candidate.to_dict() == second[-3].to_dict()


def test_repeated_ranking_ids_timestamps_groups_and_event_order_are_stable():
    matrix = {identity: STRONG_BULLISH for identity in CANONICAL_MARKET_IDENTITIES}
    event_profiles = {CANONICAL_MARKET_IDENTITIES[1]: OVERLAPPING_EVENTS_PROFILE}
    sessions = {CANONICAL_MARKET_IDENTITIES[2]: SPECIAL_SESSION_PROFILE}
    first_candidates = build_four_market_candidate_set(matrix, event_profiles_by_market=event_profiles, session_profiles_by_market=sessions)
    second_candidates = build_four_market_candidate_set(matrix, event_profiles_by_market=event_profiles, session_profiles_by_market=sessions)
    first = rank_four_market_opportunities(first_candidates); second = rank_four_market_opportunities(second_candidates)
    assert first == second and first.ranking_result_id == second.ranking_result_id
    assert first.evaluated_at == second.evaluated_at == REPLAY_EVALUATED_AT
    assert first.to_dict() == second.to_dict() and first.semantic_dict() == second.semantic_dict()
    assert first_candidates[1].external_market_context.event_context.events == second_candidates[1].external_market_context.event_context.events
    assert first_candidates[1].warnings == second_candidates[1].warnings and first_candidates[1].blockers == second_candidates[1].blockers


@pytest.mark.parametrize("scenario", (BLOCKED, UNAVAILABLE, CONFLICTING))
def test_all_ineligible_replays_are_stable(scenario):
    matrix = {identity: scenario for identity in CANONICAL_MARKET_IDENTITIES}
    first = build_ranked_four_market_result(matrix); second = build_ranked_four_market_result(matrix)
    assert first == second and first.selected_market is None and first.tie_state == "ALL_INELIGIBLE"
    assert first.rank_by_market == second.rank_by_market


def test_equal_tie_replay_is_stable_across_repeated_builds():
    matrix = {identity: STRONG_BULLISH for identity in CANONICAL_MARKET_IDENTITIES}
    first = build_ranked_four_market_result(matrix); second = build_ranked_four_market_result(matrix)
    assert first.semantic_dict() == second.semantic_dict()
    assert first.tied_markets == CANONICAL_MARKET_IDENTITIES and first.selected_market == CANONICAL_MARKET_IDENTITIES[0]
