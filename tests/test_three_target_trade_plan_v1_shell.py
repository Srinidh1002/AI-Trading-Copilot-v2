from dataclasses import FrozenInstanceError
from datetime import datetime,timezone
import pytest
from services.contracts import ThreeTargetTradePlanV1
def _p(status='READY',**x):
 d=dict(trade_plan_id='p',trade_plan_input_id='i',policy_id='q',selected_opportunity_id='o',evaluated_at=datetime(2026,1,1,tzinfo=timezone.utc),underlying_symbol='NIFTY',exchange='NSE',plan_status=status,market='NIFTY',instrument_type='INDEX_OPTION',direction='BULLISH',opportunity_confidence=.8,option_confidence=.7 if status=='READY' else None,plan_confidence=.8,invalidation_rules=('stop',) if status=='READY' else (),blockers=('blocked',) if status=='BLOCKED' else (),decision_reasons=('wait',) if status=='NO_TRADE' else ())
 d.update(x);return ThreeTargetTradePlanV1(**d)
@pytest.mark.parametrize('status',('BLOCKED','NO_TRADE'))
def test_statuses(status):assert _p(status).to_json()==_p(status).to_json()
def test_frozen_semantic():
 v=_p('BLOCKED');assert 'trade_plan_id'not in v.semantic_dict()
 with pytest.raises(FrozenInstanceError):v.market='X'
@pytest.mark.parametrize('x',[{'plan_status':'X'},{'option_confidence':None},{'blockers':('x',)},{'market':'SENSEX'}])
def test_invalid(x):
 with pytest.raises(ValueError):_p(**x)
