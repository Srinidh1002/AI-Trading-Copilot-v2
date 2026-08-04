from tests.test_paper_trading_engine_adapter_v1 import test_adapter_is_explicit_and_idempotent_for_position_evaluation
def test_durable_position_idempotency(tmp_path):test_adapter_is_explicit_and_idempotent_for_position_evaluation(tmp_path)

import pytest
from services.paper_trade_repository import PaperTradeRepository
from services.paper_trading_engine import PaperTradingEngine
from services.paper_trading import PaperTradingEngineAdapterV1,PaperTradingEngineAdapterInputV1,PaperTradePersistenceService
from services.contracts import PaperTradePositionEvaluationInputV1
from tests.p7_fixture_helpers import NOW,make_observation,make_open_position,make_open_state,make_policy

@pytest.mark.parametrize('price,expected',[(100.,'OPEN'),(101.,'OPEN'),(105.,'OPEN'),(109.,'PARTIALLY_EXITED'),(110.,'PARTIALLY_EXITED'),(111.,'PARTIALLY_EXITED'),(115.,'PARTIALLY_EXITED'),(119.,'CLOSED_TARGET_2'),(120.,'CLOSED_TARGET_2'),(121.,'CLOSED_TARGET_2'),(125.,'CLOSED_TARGET_2'),(130.,'CLOSED_TARGET_2'),(90.,'CLOSED_STOP'),(89.,'CLOSED_STOP'),(95.,'OPEN'),(99.,'OPEN'),(102.,'OPEN'),(108.,'OPEN'),(112.,'PARTIALLY_EXITED'),(118.,'PARTIALLY_EXITED'),(122.,'CLOSED_TARGET_2'),(128.,'CLOSED_TARGET_2'),(91.,'CLOSED_STOP'),(92.,'OPEN'),(93.,'OPEN'),(94.,'OPEN'),(96.,'OPEN'),(97.,'OPEN'),(98.,'OPEN'),(100.5,'OPEN')])
def test_distinct_durable_adapter_requests_preserve_single_economic_result(tmp_path,price,expected):
 service=PaperTradePersistenceService(PaperTradeRepository(tmp_path/('s'+str(price)+'.json')));adapter=PaperTradingEngineAdapterV1(PaperTradingEngine(),service)
 obs=make_observation(option_last_price=price,option_open=price,option_low=price-1,option_high=price+1,option_close=price)
 evaluation=PaperTradePositionEvaluationInputV1(make_open_position(),make_policy(allow_partial_exits=True),make_open_state(),obs,NOW,'tr','state','result',('exit-1','exit-2'),'pnl-'+str(price))
 request=PaperTradingEngineAdapterInputV1('adapter-'+str(price),'trade-'+str(price),'key-'+str(price),'EVALUATE_POSITION',NOW,position_input=evaluation)
 first=adapter.execute(request);retry=adapter.execute(request)
 assert first.status==expected and retry.duplicate and service.get(request.paper_trade_id).lifecycle_state.current_state==expected
