from tests.test_three_target_evaluation_input_v1 import _i
from tests.test_trade_planning_policy_v1 import _p
from services.trade_planning import evaluate_three_targets
def test_replay():
 i=_i();p=_p(target_method='HYBRID');a=evaluate_three_targets(i,p);b=evaluate_three_targets(i,p);assert a==b and a.to_json()==b.to_json() and a.semantic_dict()==b.semantic_dict()
