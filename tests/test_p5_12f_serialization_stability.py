"""P5-12F JSON, semantic serialization, and detached-output certification."""
from __future__ import annotations

import json
import math
from datetime import date, datetime

import pytest

from services.opportunity_ranking import evaluate_candidate_eligibility, score_market_opportunity_candidate
from tests.fixtures.p5_12 import *


def _objects(identity=CANONICAL_MARKET_IDENTITIES[0]):
    candidate = build_market_opportunity_candidate(identity, STRONG_BULLISH, event_profile=OVERLAPPING_EVENTS_PROFILE, session_profile=SPECIAL_SESSION_PROFILE)
    eligibility = evaluate_candidate_eligibility(candidate)
    score = score_market_opportunity_candidate(candidate, eligibility)
    ranking = build_ranked_four_market_result({market: STRONG_BULLISH for market in CANONICAL_MARKET_IDENTITIES})
    return (build_technical_intelligence(identity, STRONG_BULLISH), build_option_chain_intelligence(identity, STRONG_BULLISH), build_broader_market_intelligence(identity, STRONG_BULLISH), build_external_context(identity, STRONG_BULLISH, event_profile=OVERLAPPING_EVENTS_PROFILE), build_event_risk_context(identity, event_profile=OVERLAPPING_EVENTS_PROFILE), candidate.market_session_validation, candidate.market_regime, candidate.trade_opportunity, candidate, eligibility, score, ranking)


def _assert_json_safe(value):
    if isinstance(value, dict):
        for nested in value.values(): _assert_json_safe(nested)
    elif isinstance(value, list):
        for nested in value: _assert_json_safe(nested)
    elif isinstance(value, float): assert math.isfinite(value)
    else: assert value is None or type(value) in {str, int, float, bool}


def _datetime_safe_normalizer(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def _json_safe_representation(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False, default=_datetime_safe_normalizer)


def _assert_repeated_serialization_equal(left, right):
    assert left == right
    to_dict = getattr(left, "to_dict", None)
    if callable(to_dict):
        left_dict, right_dict = left.to_dict(), right.to_dict()
        left_representation = _json_safe_representation(left_dict)
        assert left_dict == right_dict
        assert left_representation == _json_safe_representation(right_dict)
        assert json.loads(left_representation) == left_dict
        _assert_json_safe(left_dict)
    to_json = getattr(left, "to_json", None)
    if callable(to_json):
        left_json, right_json = left.to_json(), right.to_json()
        assert left_json == right_json
        assert json.loads(left_json) == left.to_dict()
        assert "mappingproxy" not in left_json.lower() and "object at 0x" not in left_json.lower()
    semantic_dict = getattr(left, "semantic_dict", None)
    if callable(semantic_dict):
        semantic = semantic_dict()
        assert semantic == right.semantic_dict()
        assert json.loads(_json_safe_representation(semantic)) == semantic


def test_every_exposed_serialization_api_is_stable_and_json_safe():
    for value in _objects():
        _assert_repeated_serialization_equal(value, value)


def test_semantic_dictionaries_exclude_only_certified_presentation_fields():
    candidate = build_market_opportunity_candidate(CANONICAL_MARKET_IDENTITIES[0], STRONG_BULLISH)
    ranking = build_ranked_four_market_result({identity: STRONG_BULLISH for identity in CANONICAL_MARKET_IDENTITIES})
    assert "candidate_id" not in candidate.semantic_dict() and "evaluated_at" not in candidate.semantic_dict()
    assert "ranking_result_id" not in ranking.semantic_dict() and "evaluated_at" not in ranking.semantic_dict()
    assert candidate.to_dict()["candidate_id"] == candidate.candidate_id
    assert ranking.to_dict()["ranking_result_id"] == ranking.ranking_result_id


def test_detached_serialization_mutation_never_changes_typed_outputs():
    candidate = build_market_opportunity_candidate(CANONICAL_MARKET_IDENTITIES[0], STRONG_BULLISH, source_timestamps=build_freshness_timestamp_profile("MIXED"), event_profile=OVERLAPPING_EVENTS_PROFILE)
    baseline = candidate.to_dict(); detached = candidate.to_dict()
    detached["metadata"]["changed"] = True
    detached["source_timestamps"]["TECHNICAL"] = "changed"
    detached["warnings"].append("CHANGED")
    assert candidate.to_dict() == baseline
    assert "changed" not in candidate.metadata and "CHANGED" not in candidate.warnings
    with pytest.raises(TypeError): candidate.source_timestamps["TECHNICAL"] = REPLAY_EVALUATED_AT


def test_serialized_ranking_has_stable_market_mapping_and_paper_restrictions():
    ranking = build_ranked_four_market_result({identity: STRONG_BULLISH for identity in CANONICAL_MARKET_IDENTITIES})
    payload = json.loads(ranking.to_json())
    assert [tuple(identity) for identity, _ in payload["rank_by_market"]] == list(CANONICAL_MARKET_IDENTITIES)
    assert payload["execution_mode"] == "PAPER" and payload["live_execution_eligible"] is False
    assert payload["selected_market"] == list(ranking.selected_market)
