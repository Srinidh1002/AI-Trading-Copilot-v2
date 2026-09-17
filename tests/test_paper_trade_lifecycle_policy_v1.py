from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
import pytest
from services.contracts import PaperTradeLifecyclePolicyV1

NOW=datetime(2026,1,1,tzinfo=timezone.utc)
def make(**kw): return PaperTradeLifecyclePolicyV1('policy-1',NOW,'TEST',**kw)
def test_minimum_paper_policy_is_deterministic_and_exported():
 p=make(metadata={'b':[1],'a':{'x':2}});assert p.to_json()==p.to_json() and p.to_dict()['execution_mode']=='PAPER';assert p.semantic_dict()['policy_source']=='TEST'
def test_all_controlled_values_are_supported():
 for entry in ('ZONE_TOUCH','PREFERRED_ENTRY_TOUCH','ZONE_CLOSE'):
  for trigger in ('TOUCH','CLOSE'):
   assert make(entry_activation_mode=entry,stop_trigger_mode=trigger,target_trigger_mode=trigger).entry_activation_mode==entry
 for precedence in ('STOP_FIRST','TARGET_FIRST','CONSERVATIVE_STOP_FIRST'): assert make(same_observation_precedence=precedence).same_observation_precedence==precedence
 for mode in ('HIGHEST_CROSSED_TARGET','SEQUENTIAL_TARGETS'): assert make(multiple_target_crossing_mode=mode).multiple_target_crossing_mode==mode
 assert make(allow_partial_exits=True,runner_enabled=True,runner_close_mode='EXPIRY').runner_enabled
@pytest.mark.parametrize('field,value',[('entry_activation_mode','BAD'),('entry_zone_tolerance_fraction',-1),('entry_zone_tolerance_fraction',1.1),('entry_zone_tolerance_fraction',True),('entry_timeout_seconds',0),('maximum_observation_age_seconds',False),('maximum_holding_seconds',float('inf')),('execution_mode','LIVE'),('live_execution_eligible',True),('schema_version','2.0')])
def test_invalid_policy_values_fail_closed(field,value):
 with pytest.raises((ValueError,TypeError)): make(**{field:value})
def test_policy_coherence_and_immutability():
 with pytest.raises(ValueError):make(runner_enabled=True)
 with pytest.raises(ValueError):make(maximum_holding_seconds=1,entry_timeout_seconds=2)
 p=make(metadata={'x':[1]});d=p.to_dict();d['metadata']['x'].append(2);assert p.to_dict()['metadata']=={'x':[1]}
 with pytest.raises(FrozenInstanceError):p.policy_source='OTHER'
