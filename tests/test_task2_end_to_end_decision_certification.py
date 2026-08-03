from datetime import datetime, timezone
from services.certification.task2_decision_fixture_factory import PILLAR_ORDER, foundation_fixtures
from services.certification.task2_end_to_end_decision_certification import compose_task2_decision_certification

NOW=datetime(2026,8,3,tzinfo=timezone.utc)
def test_foundation_fixtures_are_deterministic_and_parent_cycle_coherent():
 results=tuple(compose_task2_decision_certification(value) for value in foundation_fixtures(NOW))
 assert len(results)==5
 for result in results:
  assert result.nifty.parent_cycle_id==result.sensex.parent_cycle_id==result.parent_cycle_id
  assert result.nifty.observation_id!=result.sensex.observation_id
  if result.nifty.candidate_id is not None and result.sensex.candidate_id is not None: assert result.nifty.candidate_id!=result.sensex.candidate_id
  assert result.safety_counters and all(value==0 for _,value in result.safety_counters)
 assert results[0].nifty.pre_entry_action=="CALL"
 assert results[1].sensex.pre_entry_action=="PUT"
 assert results[0].nifty.ordered_pillar_names==PILLAR_ORDER
