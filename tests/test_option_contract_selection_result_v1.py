from tests.test_option_contract_ranking_result_v1 import make_candidate,NOW
from services.contracts import OptionContractSelectionResultV1
def _r(**x):
 d=dict(selection_result_id='r',selection_id='s',evaluated_at=NOW,underlying_symbol='NIFTY',exchange='NSE',direction='BULLISH',option_right='CALL',status='READY',selected_contract=make_candidate(),selected_rank=1,selected_score=.8,premium_affordable=True,spread_acceptable=True,liquidity_acceptable=True,open_interest_acceptable=True,volume_acceptable=True,moneyness_acceptable=True,expiry_acceptable=True,lot_size_acceptable=True,session_acceptable=True,event_acceptable=True,estimated_one_lot_premium_cost=2500.,affordable_lot_count=3);d.update(x);return OptionContractSelectionResultV1(**d)
def test_ready_properties_and_json():assert _r().selected_trading_symbol=='c1-SYMBOL' and _r().to_json()==_r().to_json()
def test_statuses():assert _r(status='BLOCKED',selected_contract=None,selected_rank=None,selected_score=None,blockers=('X',)).status=='BLOCKED';assert _r(status='NO_CONTRACT',selected_contract=None,selected_rank=None,selected_score=None,decision_reasons=('X',)).status=='NO_CONTRACT'
