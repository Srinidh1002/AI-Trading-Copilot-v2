from services.paper_trading_engine import PaperTradingEngine
def test_legacy_engine_remains_unmodified_by_wp4():
 engine=PaperTradingEngine();assert engine.count_trades()==0 and engine.count_open_trades()==0
