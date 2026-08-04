from services.broader_market_intelligence import build_broader_market_intelligence
from tests.fixtures.broader_market_intelligence import NOW,series
def test_insufficient_returns_fail_closed():
 result=build_broader_market_intelligence(primary_series=series("NIFTY","NSE",(.01,)),related_series=series("SENSEX","BSE",(.01,)),created_at=NOW,cross_market_evidence_id="cross",result_id="result")
 assert result.intelligence_status=="BLOCKED";assert result.aggregate_strength==0
