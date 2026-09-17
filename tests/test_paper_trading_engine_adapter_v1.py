from services.paper_trade_repository import PaperTradeRepository
from services.paper_trading_engine import PaperTradingEngine
from services.paper_trading import PaperTradingEngineAdapterV1,PaperTradingEngineAdapterInputV1,PaperTradePersistenceService
from services.contracts import PaperTradePositionEvaluationInputV1
from tests.p7_fixture_helpers import NOW,make_observation,make_open_position,make_open_state,make_policy
def test_adapter_is_explicit_and_idempotent_for_position_evaluation(tmp_path):
 persistence=PaperTradePersistenceService(PaperTradeRepository(tmp_path/'typed.json'));engine=PaperTradingEngine();adapter=PaperTradingEngineAdapterV1(engine,persistence)
 evaluation=PaperTradePositionEvaluationInputV1(make_open_position(),make_policy(allow_partial_exits=True),make_open_state(),make_observation(option_last_price=110.,option_open=110.,option_low=109.,option_high=111.,option_close=110.),NOW,'transition','next-state','eval',('exit-1','exit-2'),'pnl-1')
 request=PaperTradingEngineAdapterInputV1('adapter-result','typed-position','key-1','EVALUATE_POSITION',NOW,position_input=evaluation)
 first=adapter.execute(request);second=adapter.execute(request)
 assert first.status=='PARTIALLY_EXITED' and second.duplicate and engine.count_trades()==0

def test_adapter_persists_typed_cancellation_without_legacy_close(tmp_path):
 persistence=PaperTradePersistenceService(PaperTradeRepository(tmp_path/'typed.json'));engine=PaperTradingEngine();adapter=PaperTradingEngineAdapterV1(engine,persistence)
 evaluation=PaperTradePositionEvaluationInputV1(make_open_position(),make_policy(allow_partial_exits=True),make_open_state(),make_observation(),NOW,'cancel-transition','cancel-state','cancel-eval',('cancel-fill',),'cancel-pnl',cancellation_status='REQUESTED',cancellation_reason_code='USER_REQUEST')
 request=PaperTradingEngineAdapterInputV1('cancel-result','typed-cancel','cancel-key','CANCEL_PAPER_TRADE',NOW,position_input=evaluation)
 first=adapter.execute(request);second=adapter.execute(request)
 assert first.status=='CANCELLED' and second.duplicate and persistence.get('typed-cancel').lifecycle_state.current_state=='CANCELLED' and engine.count_trades()==0
