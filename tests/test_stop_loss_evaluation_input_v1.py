from dataclasses import FrozenInstanceError
from datetime import datetime,timezone
import pytest
from services.contracts import StopLossEvaluationInputV1
T=datetime(2026,1,2,tzinfo=timezone.utc)
def _s(**x):
 d=dict(evaluation_id='e',evaluation_result_id='r',evaluated_at=T,trade_plan_input_id='p',policy_id='P',entry_evaluation_result_id='er',underlying_symbol='NIFTY',exchange='NSE',direction='BULLISH',option_right='CALL',entry_reference_price=100.,entry_zone_lower=99.,entry_zone_upper=101.,atr_value=10.,structure_stop_price=95.,premium_reference_price=100.,recent_swing_low=96.,recent_swing_high=105.,planning_allowed=True,source_timestamps={'x':T},metadata={'n':{'x':1}});d.update(x);return StopLossEvaluationInputV1(**d)
@pytest.mark.parametrize('symbol,exchange,direction,right',[('NIFTY','NSE','BULLISH','CALL'),('BANKNIFTY','NSE','BEARISH','PUT'),('FINNIFTY','NSE','BULLISH','CALL'),('SENSEX','BSE','BEARISH','PUT')])
def test_valid_identities(symbol,exchange,direction,right):assert _s(underlying_symbol=symbol,exchange=exchange,direction=direction,option_right=right).to_json()==_s(underlying_symbol=symbol,exchange=exchange,direction=direction,option_right=right).to_json()
def test_detached_and_frozen():
 v=_s();d=v.to_dict();d['metadata']['n']['x']=2;assert v.metadata['n']['x']==1
 with pytest.raises(FrozenInstanceError):v.policy_id='x'
@pytest.mark.parametrize('field,value',[('entry_reference_price',0),('entry_zone_lower',101.),('planning_allowed',1),('execution_mode','LIVE')])
def test_invalid(field,value):
 with pytest.raises((ValueError,TypeError)):_s(**{field:value})
