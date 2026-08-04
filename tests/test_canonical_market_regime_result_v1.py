from datetime import datetime,timezone
from services.contracts.canonical_market_regime_result_v1 import CanonicalMarketRegimeResultV1
def test_unavailable_regime_result_serializes():
 t=datetime(2026,1,1,tzinfo=timezone.utc);assert CanonicalMarketRegimeResultV1("r",t,"NIFTY","NSE",None,None,None,None,"UNAVAILABLE","UNAVAILABLE","UNAVAILABLE","UNAVAILABLE","UNAVAILABLE","UNAVAILABLE","UNAVAILABLE",0,0,0,4,0,0).to_json()
