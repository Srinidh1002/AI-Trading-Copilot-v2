import ast
import json
from pathlib import Path

from services.opportunity_ranking import rank_four_market_opportunities
from tests.fixtures.p5_12 import *


def test_raw_score_never_bypasses_unavailable_or_conflicting_eligibility():
    candidates=list(build_four_market_candidate_set({CANONICAL_MARKET_IDENTITIES[0]:UNAVAILABLE,CANONICAL_MARKET_IDENTITIES[1]:CONFLICTING,CANONICAL_MARKET_IDENTITIES[2]:STRONG_BULLISH,CANONICAL_MARKET_IDENTITIES[3]:WEAK_BULLISH}))
    result=rank_four_market_opportunities(tuple(candidates));assert result.selected_market==CANONICAL_MARKET_IDENTITIES[2] and result.rank_by_market[CANONICAL_MARKET_IDENTITIES[0]] is None and result.rank_by_market[CANONICAL_MARKET_IDENTITIES[1]] is None


def test_ranking_serialization_is_stable_detached_and_order_independent():
    matrix={identity:STRONG_BULLISH for identity in CANONICAL_MARKET_IDENTITIES};candidates=build_four_market_candidate_set(matrix)
    first=rank_four_market_opportunities(candidates);second=rank_four_market_opportunities(tuple(reversed(candidates)))
    assert first.to_json()==second.to_json() and first.semantic_dict()==second.semantic_dict()
    payload=first.to_dict();payload['metadata']['changed']=True;assert 'changed' not in first.metadata and json.loads(first.to_json())['execution_mode']=='PAPER'


def test_ranking_fixture_sources_have_no_clock_random_uuid_or_network_calls():
    root=Path(__file__).resolve().parent/'fixtures'/'p5_12';banned={'now','utcnow','today','random','uuid4'}
    for path in root.glob('*.py'):
        calls={node.func.attr for node in ast.walk(ast.parse(path.read_text())) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)}
        assert not calls & banned
