from datetime import datetime,timezone
from dataclasses import FrozenInstanceError
import pytest
from services.contracts import CapitalQuantityPlanningPolicyV1
NOW=datetime(2026,7,29,tzinfo=timezone.utc)
def _p(**x):
 d=dict(policy_id='P6I',maximum_capital_utilization_fraction=.8,maximum_risk_fraction=.01,maximum_planned_lot_count=3,policy_timestamp=NOW);d.update(x);return CapitalQuantityPlanningPolicyV1(**d)
def test_valid_modes_export_and_stability():
 p=_p(target_allocation_enabled=True,target_allocation_weights=(.3,.4,.3));assert p.target_remainder_priority==('T1','T2','T3') and p.to_json()==p.to_json() and p.semantic_dict()['risk_model']=='PREMIUM_AT_RISK'
 assert _p(risk_model='CALLER_SUPPLIED_PER_LOT_RISK',maximum_risk_fraction=None,maximum_risk_amount=10).maximum_risk_amount==10.
@pytest.mark.parametrize('k,v',[('maximum_capital_utilization_fraction',0),('maximum_capital_utilization_fraction',True),('maximum_risk_fraction',None),('maximum_risk_amount',0),('minimum_planned_lot_count',False),('maximum_planned_lot_count',0),('target_allocation_weights',(1,)),('target_allocation_enabled',True)])
def test_invalid(k,v):
 d={k:v}
 if k=='maximum_risk_fraction':d['maximum_risk_amount']=None
 if k=='target_allocation_enabled':d['target_allocation_weights']=()
 with pytest.raises((ValueError,TypeError)):_p(**d)
def test_immutable_detached_and_paper():
 m={'nested':[1]};p=_p(metadata=m,warnings=('A','A'));m['nested'].append(2);assert p.metadata['nested']==(1,) and p.warnings==('A',)
 with pytest.raises(FrozenInstanceError):p.policy_id='x'
 assert p.execution_mode=='PAPER' and p.live_execution_eligible is False
