from tests.test_canonical_trade_plan_input_v1 import _value
from tests.test_entry_zone_evaluation_result_v1 import _result
from tests.test_stop_loss_evaluation_input_v1 import _s
from tests.test_trade_planning_policy_v1 import _p
from services.trade_planning import evaluate_stop_loss
def _run(method='ATR',**x):
 d={'trade_plan_input_id':'p6b-NIFTY','policy_id':'P','entry_evaluation_result_id':'entry-result-1'};d.update(x);i=_s(**d);return evaluate_stop_loss(_value(('NIFTY','NSE')),_p(stop_loss_method=method,stop_loss_premium_fraction=.1 if method=='PREMIUM_FRACTION' else None),_result(),i)
def test_atr_formula():
 r=_run('ATR');assert (r.stop_loss_price,r.stop_distance_fraction,r.selected_stop_source)==(90.,.1,'ATR')
def test_structure_and_premium():assert _run('STRUCTURE').selected_stop_source=='STRUCTURE_STOP';assert _run('PREMIUM_FRACTION',atr_value=None).selected_stop_source=='PREMIUM_FRACTION'
def test_bounds_and_missing():assert _run('ATR',atr_value=.5).blockers==('STOP_DISTANCE_OUT_OF_RANGE',);assert _run('ATR',atr_value=None).blockers==('STOP_REFERENCE_UNAVAILABLE',)
def test_hybrid_tightest_and_fallback():
 r=_run('HYBRID',structure_stop_price=None,recent_swing_low=None);assert r.selected_stop_source=='ATR' and r.warnings==('STOP_HYBRID_FALLBACK_USED',)
def test_early_order():assert _run('ATR',planning_allowed=False,blockers=('INPUT',),policy_id='BAD').blockers==('INPUT','STOP_PLANNING_NOT_ALLOWED','STOP_POLICY_MISMATCH')
