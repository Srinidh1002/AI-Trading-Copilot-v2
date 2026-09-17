from services.contracts import PaperTradePositionEvaluationInputV1
from tests.p7_fixture_helpers import NOW,make_observation,make_open_position,make_open_state,make_policy
import math, pytest
def test_input_real_contracts():
 x=PaperTradePositionEvaluationInputV1(make_open_position(),make_policy(),make_open_state(),make_observation(),NOW,'transition','result-state','result',('exit-1','exit-2'),'pnl-1')
 assert x.position.position_id=='position-1'

def test_tri_state_invalidation_authority_and_serialization():
 base=dict(position=make_open_position(),lifecycle_policy=make_policy(),lifecycle_state=make_open_state(),observation=make_observation(),evaluation_timestamp=NOW,requested_transition_id='transition',resulting_lifecycle_state_id='result-state',evaluation_result_id='result',exit_fill_ids=('exit-1',),pnl_evidence_id='pnl-1')
 assert PaperTradePositionEvaluationInputV1(**base).invalidation_status=='ABSENT'
 triggered=PaperTradePositionEvaluationInputV1(**base,invalidation_status='TRIGGERED',invalidation_reason_code='RISK_INVALID')
 assert triggered.semantic_dict()['invalidation_reason_code']=='RISK_INVALID'
 import pytest
 for changes in ({'invalidation_status':'BAD'},{'invalidation_status':True},{'invalidation_status':'TRIGGERED'},{'invalidation_status':'ABSENT','invalidation_reason_code':'X'}):
  with pytest.raises((TypeError,ValueError)):PaperTradePositionEvaluationInputV1(**base,**changes)

def base_values():
 return dict(position=make_open_position(),lifecycle_policy=make_policy(),lifecycle_state=make_open_state(),observation=make_observation(),evaluation_timestamp=NOW,requested_transition_id='transition',resulting_lifecycle_state_id='result-state',evaluation_result_id='result',exit_fill_ids=('exit-1',),pnl_evidence_id='pnl-1')
@pytest.mark.parametrize('field',('target_1_exit_cost','target_2_exit_cost','target_3_exit_cost','stop_exit_cost','session_exit_cost','expiry_exit_cost','invalidation_exit_cost','runner_exit_cost'))
@pytest.mark.parametrize('value,ok',((0.,True),(1.25,True),(-1.,False),(True,False),(math.nan,False),(math.inf,False),(-math.inf,False)))
def test_each_exit_cost_is_strictly_finite_nonnegative(field,value,ok):
 if ok:assert PaperTradePositionEvaluationInputV1(**base_values(),**{field:value})
 else:
  with pytest.raises((TypeError,ValueError)):PaperTradePositionEvaluationInputV1(**base_values(),**{field:value})
@pytest.mark.parametrize('field',('requested_transition_id','resulting_lifecycle_state_id','evaluation_result_id','pnl_evidence_id'))
@pytest.mark.parametrize('value',('', ' ',None,True,1,{}))
def test_caller_identity_fields_are_nonblank_exact_strings(field,value):
 with pytest.raises((TypeError,ValueError)):PaperTradePositionEvaluationInputV1(**base_values(),**{field:value})
def test_fill_ids_cannot_reuse_entry_fill_and_serialization_is_stable():
 with pytest.raises(ValueError):PaperTradePositionEvaluationInputV1(**(base_values()|{'exit_fill_ids':('fill-1',)}))
 x=PaperTradePositionEvaluationInputV1(**base_values(),metadata={'nested':[1]});d=x.to_dict();d['metadata']['nested'].append(2)
 assert x.to_json()==x.to_json() and x.semantic_dict()['pnl_evidence_id']=='pnl-1' and x.to_dict()['metadata']=={'nested':[1]}
