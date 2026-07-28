from services.broader_market_intelligence import build_broader_market_intelligence
from tests.fixtures.broader_market_intelligence import NOW,series
def test_identical_replay_is_semantically_stable():
 kwargs=dict(primary_series=series("NIFTY","NSE"),related_series=series("SENSEX","BSE"),created_at=NOW,cross_market_evidence_id="cross",result_id="result")
 assert build_broader_market_intelligence(**kwargs).semantic_dict()==build_broader_market_intelligence(**kwargs).semantic_dict()
