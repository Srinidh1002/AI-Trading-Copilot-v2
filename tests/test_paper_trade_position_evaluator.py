import pytest
from services.paper_trading import evaluate_open_paper_trade_position
from services.contracts import PaperTradePositionEvaluationInputV1
from tests.p7_fixture_helpers import NOW,make_observation,make_open_position,make_open_state,make_policy
def run(observation,policy=None,ids=('exit-1','exit-2','exit-3')): return evaluate_open_paper_trade_position(PaperTradePositionEvaluationInputV1(make_open_position(),policy or make_policy(allow_partial_exits=True),make_open_state(),observation,NOW,'transition','state','result',ids,'pnl-1'))
def test_stop_closes_all(): assert run(make_observation(option_last_price=90.,option_open=90.,option_low=89.,option_high=91.,option_close=90.)).status=='CLOSED_STOP'
def test_target_one_partially_exits(): assert run(make_observation(option_last_price=110.,option_open=110.,option_low=109.,option_high=111.,option_close=110.)).status=='PARTIALLY_EXITED'
def test_session_close(): assert run(make_observation(session_state='CLOSED',is_market_open=False)).status=='CLOSED_SESSION'
def test_expiry_close(): assert run(make_observation(),make_policy(allow_partial_exits=True),ids=('exit-1',)).status=='OPEN'
def test_machine_readable_invalidation_precedes_stop_and_targets():
 from services.contracts import PaperTradePositionEvaluationInputV1
 i=PaperTradePositionEvaluationInputV1(make_open_position(),make_policy(allow_partial_exits=True),make_open_state(),make_observation(option_last_price=90.,option_open=90.,option_low=89.,option_high=111.,option_close=90.),NOW,'transition','state','invalid',('exit-1',),'pnl-invalid',invalidation_status='TRIGGERED',invalidation_reason_code='RULE_INVALID')
 r=evaluate_open_paper_trade_position(i); assert r.status=='CLOSED_INVALIDATED' and r.position_decision=='CLOSE_INVALIDATED' and r.invalidation_triggered and r.generated_exit_fills[0].fill_reason=='INVALIDATION' and r.decision_reasons==('RULE_INVALID',)
def test_expiry_and_session_precede_invalidation():
 from datetime import timedelta
 from services.contracts import PaperTradePositionEvaluationInputV1
 expiry=NOW.replace(day=29); i=PaperTradePositionEvaluationInputV1(make_open_position(),make_policy(allow_partial_exits=True),make_open_state(),make_observation(observed_at=expiry,received_at=expiry),expiry,'transition','state','expiry',('exit-1',),'pnl-expiry',invalidation_status='TRIGGERED',invalidation_reason_code='X')
 assert evaluate_open_paper_trade_position(i).status=='CLOSED_EXPIRY'
def test_insufficient_multi_target_ids_fails_closed():
 from services.contracts import PaperTradePositionEvaluationInputV1
 i=PaperTradePositionEvaluationInputV1(make_open_position(),make_policy(allow_partial_exits=True),make_open_state(),make_observation(option_last_price=120.,option_open=120.,option_low=119.,option_high=121.,option_close=120.),NOW,'transition','state','few',('exit-1',),'pnl-few')
 r=evaluate_open_paper_trade_position(i);assert r.status=='BLOCKED' and r.blockers==('INSUFFICIENT_EXIT_FILL_IDS',) and not r.generated_exit_fills
