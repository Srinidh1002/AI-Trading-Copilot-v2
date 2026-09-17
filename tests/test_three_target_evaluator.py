from tests.test_three_target_evaluation_input_v1 import _i
from tests.test_trade_planning_policy_v1 import _p
from services.trade_planning import evaluate_three_targets
def test_risk_multiple():
 r=evaluate_three_targets(_i(),_p(target_method='RISK_MULTIPLE'));assert [x.target_price for x in (r.target_1,r.target_2,r.target_3)]==[110.,115.,120.] and r.weighted_reward_to_risk==1.5
def test_methods():
 for m in ('ATR','EXPECTED_MOVE','STRUCTURE','HYBRID'):assert evaluate_three_targets(_i(),_p(target_method=m)).status=='READY'
