from dataclasses import FrozenInstanceError
import math, pytest
from services.contracts import TradePlanTargetV1

def _target(number=1, **changes):
    roles={1:'RISK_REDUCTION',2:'PRIMARY',3:'EXTENDED'}
    values=dict(target_number=number,target_price=100.,allocation_fraction=.3,reward_amount_per_unit=20.,reward_to_risk=1.,target_role=roles[number])
    values.update(changes); return TradePlanTargetV1(**values)

@pytest.mark.parametrize('number', (1,2,3))
def test_valid_targets(number):
    value=_target(number); assert value.target_role and value.to_json()==value.to_json()==_target(number).to_json()
def test_frozen_and_detached():
    value=_target(); payload=value.to_dict(); payload['target_price']=1
    assert value.target_price==100.
    with pytest.raises(FrozenInstanceError): value.target_price=1
@pytest.mark.parametrize('changes',[{'target_number':True},{'target_number':4},{'target_role':'PRIMARY'},{'target_price':0},{'allocation_fraction':1.1},{'reward_amount_per_unit':0},{'reward_to_risk':math.inf},{'target_price':True},{'schema_version':'2.0'}])
def test_invalid_targets(changes):
    with pytest.raises(ValueError): _target(**changes)
