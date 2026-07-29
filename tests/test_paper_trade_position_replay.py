from services.paper_trading import evaluate_open_paper_trade_position
from services.contracts import PaperTradePositionEvaluationInputV1
from tests.p7_fixture_helpers import NOW,make_observation,make_open_position,make_open_state,make_policy
def test_replay_is_deterministic():
 i=PaperTradePositionEvaluationInputV1(make_open_position(),make_policy(allow_partial_exits=True),make_open_state(),make_observation(option_last_price=110.,option_open=110.,option_low=109.,option_high=111.,option_close=110.),NOW,'transition','state','result',('exit-1','exit-2'),'pnl-replay')
 assert len({evaluate_open_paper_trade_position(i).to_json() for _ in range(10)})==1

def test_real_output_lifecycle_snapshot_chains_t1_to_t2():
 from datetime import timedelta
 first=PaperTradePositionEvaluationInputV1(make_open_position(),make_policy(allow_partial_exits=True),make_open_state(),make_observation(observation_id='t1',option_last_price=110.,option_open=110.,option_low=109.,option_high=111.,option_close=110.),NOW,'t1-transition','state-t1','t1-result',('t1-fill','t2-fill'),'t1-pnl')
 r1=evaluate_open_paper_trade_position(first)
 assert r1.resulting_lifecycle_state.current_state=='PARTIALLY_EXITED' and r1.resulting_position.lifecycle_state==r1.resulting_lifecycle_state_name
 later=NOW+timedelta(seconds=1);obs=make_observation(observation_id='t2',observed_at=later,received_at=later,option_last_price=120.,option_open=120.,option_low=119.,option_high=121.,option_close=120.)
 second=PaperTradePositionEvaluationInputV1(r1.resulting_position,make_policy(allow_partial_exits=True),r1.resulting_lifecycle_state,obs,later,'t2-transition','state-t2','t2-result',('t2-fill',),'t2-pnl')
 r2=evaluate_open_paper_trade_position(second)
 assert r2.resulting_lifecycle_state.current_state=='CLOSED_TARGET_2' and [f.fill_reason for f in r2.resulting_position.exit_fills]==['TARGET_1','TARGET_2']
 assert r2.pnl_evidence.allocated_entry_cost_before==r1.pnl_evidence.allocated_entry_cost_after
