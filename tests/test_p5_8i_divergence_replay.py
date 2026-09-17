from services.broader_market_intelligence import build_broader_market_intelligence
from tests.fixtures.broader_market_intelligence import NOW,series
def test_strong_directional_divergence_is_not_ready():
 result=build_broader_market_intelligence(primary_series=series("NIFTY","NSE",tuple(.01 for _ in range(30))),related_series=series("SENSEX","BSE",tuple(-.01 for _ in range(30))),created_at=NOW,cross_market_evidence_id="cross",result_id="result")
 assert result.intelligence_status in {"CONFLICTING","BLOCKED"};assert result.intelligence_status!="READY"
