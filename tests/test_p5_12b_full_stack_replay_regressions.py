import json

from tests.fixtures.p5_12 import *


def test_rejected_and_conflicting_fixture_candidates_are_fail_closed_and_visible():
 for scenario,state in ((BLOCKED,'BLOCKED'),(UNAVAILABLE,'UNAVAILABLE'),(CONFLICTING,'CONFLICTING')):
  scenarios={identity:scenario for identity in CANONICAL_MARKET_IDENTITIES}
  result=build_ranked_four_market_result(scenarios)
  assert all(result.eligibility_by_market[identity] in {state,'UNAVAILABLE','BLOCKED'} for identity in CANONICAL_MARKET_IDENTITIES)
  if scenario.blocked or scenario.unavailable:assert result.selected_market is None


def test_full_stack_output_is_deterministic_json_safe_and_paper_only():
 scenarios={identity:STRONG_BULLISH for identity in CANONICAL_MARKET_IDENTITIES}
 first=build_ranked_four_market_result(scenarios); second=build_ranked_four_market_result(scenarios)
 assert first.to_dict()==second.to_dict() and first.to_json()==second.to_json()
 assert json.loads(first.to_json())['execution_mode']=='PAPER'
 payload=first.to_dict();payload['metadata']['pipeline_version']='changed'
 assert first.metadata['pipeline_version']=='P5-11H'
