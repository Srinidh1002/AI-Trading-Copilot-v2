from services.paper_trading import evaluate_open_paper_trade_position
from services.contracts import PaperTradePositionEvaluationInputV1
from tests.p7_fixture_helpers import NOW,make_observation,make_open_position,make_open_state,make_policy
def test_hold_result():
 r=evaluate_open_paper_trade_position(PaperTradePositionEvaluationInputV1(make_open_position(),make_policy(),make_open_state(),make_observation(),NOW,'transition','state','result',('exit-1',),'pnl-1'))
 assert r.status=='OPEN' and r.position_decision=='HOLD'
