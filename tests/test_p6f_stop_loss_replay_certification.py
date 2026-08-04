"""Fixed, deterministic replay certification for the P6F stop boundary."""
import pytest
from tests.test_canonical_trade_plan_input_v1 import _value
from tests.test_entry_zone_evaluation_result_v1 import _result
from tests.test_stop_loss_evaluation_input_v1 import _s
from tests.test_trade_planning_policy_v1 import _p
from services.trade_planning import evaluate_stop_loss

CASES=(
 ('NIFTY','NSE','BULLISH','CALL','ATR',{},'READY','ATR',()),
 ('BANKNIFTY','NSE','BEARISH','PUT','STRUCTURE',{},'READY','STRUCTURE_STOP',()),
 ('FINNIFTY','NSE','BULLISH','CALL','PREMIUM_FRACTION',{},'READY','PREMIUM_FRACTION',()),
 ('SENSEX','BSE','BEARISH','PUT','HYBRID',{'structure_stop_price':None,'recent_swing_low':None},'READY','ATR',()),
 ('NIFTY','NSE','BULLISH','CALL','ATR',{'planning_allowed':False},'BLOCKED',None,('STOP_PLANNING_NOT_ALLOWED',)),
 ('BANKNIFTY','NSE','BEARISH','PUT','ATR',{'policy_id':'BAD'},'BLOCKED',None,('STOP_POLICY_MISMATCH',)),
 ('FINNIFTY','NSE','BULLISH','CALL','ATR',{'atr_value':None},'BLOCKED',None,('STOP_REFERENCE_UNAVAILABLE',)),
 ('SENSEX','BSE','BEARISH','PUT','ATR',{'atr_value':100.},'BLOCKED',None,('STOP_PRICE_INVALID',)),
 ('NIFTY','NSE','BULLISH','CALL','HYBRID',{'atr_value':.1,'structure_stop_price':None,'recent_swing_low':None},'BLOCKED',None,('STOP_POLICY_CONSTRAINT_FAILED',)),
)
@pytest.mark.parametrize('symbol,exchange,direction,right,method,overrides,status,source,blockers',CASES)
def test_fixed_replay_matrix(symbol,exchange,direction,right,method,overrides,status,source,blockers):
 plan=_value((symbol,exchange));entry=_result(underlying_symbol=symbol,exchange=exchange,direction=direction,option_right=right)
 values={'trade_plan_input_id':plan.trade_plan_input_id,'policy_id':'P','entry_evaluation_result_id':entry.evaluation_result_id,'underlying_symbol':symbol,'exchange':exchange,'direction':direction,'option_right':right};values.update(overrides);i=_s(**values)
 p=_p(stop_loss_method=method,stop_loss_premium_fraction=.1 if method=='PREMIUM_FRACTION' else None)
 a,b=evaluate_stop_loss(plan,p,entry,i),evaluate_stop_loss(plan,p,entry,i)
 assert a==b and a.to_json()==b.to_json() and a.semantic_dict()==b.semantic_dict()
 assert (a.status,a.selected_stop_source,a.blockers)==(status,source,blockers)
 assert (a.evaluation_result_id,a.evaluated_at,a.execution_mode,a.live_execution_eligible)==(i.evaluation_result_id,i.evaluated_at,'PAPER',False)
 assert dict(a.source_timestamps)==dict(i.source_timestamps) and i.to_json()==i.to_json()
 if method=='HYBRID' and status=='READY':assert a.warnings==('STOP_HYBRID_FALLBACK_USED',)
