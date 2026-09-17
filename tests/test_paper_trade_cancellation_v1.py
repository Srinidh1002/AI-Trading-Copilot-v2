import pytest
from datetime import timedelta
from services.contracts import PaperTradePositionEvaluationInputV1
from services.paper_trading import evaluate_open_paper_trade_position
from tests.p7_fixture_helpers import NOW,make_observation,make_open_position,make_open_state,make_policy
def request(**changes):
 v=dict(position=make_open_position(),lifecycle_policy=make_policy(allow_partial_exits=True),lifecycle_state=make_open_state(),observation=make_observation(),evaluation_timestamp=NOW,requested_transition_id='cancel-transition',resulting_lifecycle_state_id='cancel-state',evaluation_result_id='cancel-result',exit_fill_ids=('cancel-fill',),pnl_evidence_id='cancel-pnl',cancellation_status='REQUESTED',cancellation_reason_code='USER_REQUEST')
 v.update(changes);return PaperTradePositionEvaluationInputV1(**v)
def test_cancellation_closes_remaining_position_with_typed_evidence():
 result=evaluate_open_paper_trade_position(request())
 assert result.status=='CANCELLED' and result.position_decision=='CANCEL' and result.cancellation_triggered and result.resulting_position.remaining_quantity==0 and result.generated_exit_fills[0].fill_reason=='CANCELLED'
@pytest.mark.parametrize('status,reason', [('BAD',None),('REQUESTED',None),('REQUESTED',' '),('ABSENT','X'),('NOT_REQUESTED','X')])
def test_cancellation_input_is_controlled(status,reason):
 with pytest.raises((TypeError,ValueError)):request(cancellation_status=status,cancellation_reason_code=reason)
def test_cancellation_precedes_invalidation_stop_and_targets_but_not_session():
 conflict=request(observation=make_observation(option_last_price=90.,option_open=90.,option_low=89.,option_high=121.,option_close=90.),invalidation_status='TRIGGERED',invalidation_reason_code='INVALID')
 assert evaluate_open_paper_trade_position(conflict).status=='CANCELLED'
 session=request(observation=make_observation(session_state='CLOSED',is_market_open=False))
 assert evaluate_open_paper_trade_position(session).status=='CLOSED_SESSION'
def test_cancellation_cost_is_strict_and_used():
 result=evaluate_open_paper_trade_position(request(cancellation_exit_cost=2.5))
 assert result.generated_exit_fills[0].estimated_trading_cost==2.5
 for bad in (True,-1.,float('nan'),float('inf')):
  with pytest.raises((TypeError,ValueError)):request(cancellation_exit_cost=bad)
