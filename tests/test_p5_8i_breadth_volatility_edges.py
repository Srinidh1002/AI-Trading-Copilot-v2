from services.broader_market_intelligence import build_broader_market_intelligence
from tests.fixtures.broader_market_intelligence import NOW,series,breadth,volatility
def test_zero_declines_and_high_volatility_warning():
 result=build_broader_market_intelligence(primary_series=series("NIFTY","NSE"),related_series=series("SENSEX","BSE"),breadth_snapshot=breadth("NIFTY","NSE",60,0,40),volatility_snapshot=volatility("NIFTY","NSE","HIGH",5),created_at=NOW,cross_market_evidence_id="cross",breadth_evidence_id="breadth",volatility_context_id="vix",result_id="result")
 assert result.breadth_evidence.advance_decline_ratio is None;assert result.volatility_context.volatility_regime=="HIGH"
