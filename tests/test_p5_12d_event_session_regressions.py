import ast
import json
from pathlib import Path

from services.opportunity_ranking import evaluate_candidate_eligibility, rank_four_market_opportunities, score_market_opportunity_candidate
from tests.fixtures.p5_12 import *


def test_overlap_preserves_blocking_and_warning_reasons_without_duplicates():
    candidate=build_market_opportunity_candidate(CANONICAL_MARKET_IDENTITIES[0],STRONG_BULLISH,event_profile=OVERLAPPING_EVENTS_PROFILE)
    assert candidate.candidate_status=='BLOCKED' and candidate.blockers and candidate.warnings
    assert len(candidate.blockers)==len(set(candidate.blockers)) and len(candidate.warnings)==len(set(candidate.warnings))
    assert not evaluate_candidate_eligibility(candidate).rankable


def test_event_and_session_restrictions_remain_separate_and_deterministic():
    candidate=build_market_opportunity_candidate(CANONICAL_MARKET_IDENTITIES[0],STRONG_BULLISH,event_profile=CPI_WARNING_EVENT_PROFILE,session_profile=HOLIDAY_SESSION)
    assert candidate.candidate_status=='BLOCKED' and 'P512_HOLIDAY' in candidate.blockers and 'P512_CPI_WARNING' in candidate.warnings
    first=candidate.to_dict();second=candidate.to_dict();assert first==second
    first['metadata']['changed']=True;assert 'changed' not in candidate.metadata


def test_event_penalty_and_input_order_independence():
    clean=build_market_opportunity_candidate(CANONICAL_MARKET_IDENTITIES[0],STRONG_BULLISH)
    warning=build_market_opportunity_candidate(CANONICAL_MARKET_IDENTITIES[1],STRONG_BULLISH,event_profile=CPI_WARNING_EVENT_PROFILE)
    clean_score=score_market_opportunity_candidate(clean,evaluate_candidate_eligibility(clean));warning_score=score_market_opportunity_candidate(warning,evaluate_candidate_eligibility(warning))
    assert 'EVENT_RISK' not in clean_score.applied_penalties and list(warning_score.applied_penalties).count('EVENT_RISK')<=1
    matrix={identity:STRONG_BULLISH for identity in CANONICAL_MARKET_IDENTITIES}
    first=build_four_market_candidate_set(matrix,event_profiles_by_market={CANONICAL_MARKET_IDENTITIES[1]:CPI_WARNING_EVENT_PROFILE})
    assert rank_four_market_opportunities(first).semantic_dict()==rank_four_market_opportunities(tuple(reversed(first))).semantic_dict()


def test_fixture_sources_remain_isolated_from_clock_random_and_network_calls():
    root=Path(__file__).resolve().parent/'fixtures'/'p5_12';banned={'now','utcnow','today','random','uuid4'}
    for path in root.glob('*.py'):
        calls={node.func.attr for node in ast.walk(ast.parse(path.read_text())) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)}
        assert not calls & banned
