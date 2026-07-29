import inspect
from services.paper_trading_engine import PaperTradingEngine
from services.paper_trading import PaperTradingEngineAdapterV1
def test_adapter_is_explicit_and_engine_public_signature_is_unchanged():
 assert 'pipeline_result' in inspect.signature(PaperTradingEngine.open_trade).parameters
 assert PaperTradingEngine().count_trades()==0
 assert isinstance(PaperTradingEngineAdapterV1(PaperTradingEngine()),PaperTradingEngineAdapterV1)
