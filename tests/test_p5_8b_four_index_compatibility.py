from datetime import datetime,timezone
import pytest
from services.contracts.cross_market_evidence_v1 import CrossMarketEvidenceV1
NOW=datetime(2026,1,1,tzinfo=timezone.utc)
@pytest.mark.parametrize(("symbol","exchange","related","related_exchange","relationship"),(("NIFTY","NSE","SENSEX","BSE","BROAD_MARKET"),("SENSEX","BSE","NIFTY","NSE","BROAD_MARKET"),("BANKNIFTY","NSE","FINNIFTY","NSE","FINANCIAL_INDEX"),("FINNIFTY","NSE","BANKNIFTY","NSE","FINANCIAL_INDEX")))
def test_canonical_pair_compatibility(symbol,exchange,related,related_exchange,relationship):
 result=CrossMarketEvidenceV1("id",NOW,symbol,exchange,related,related_exchange,relationship,"5m",2,2,.5,.5,"MODERATE_POSITIVE","BULLISH","BULLISH","CONFIRMING","NONE","READY","a","b",NOW,NOW)
 assert (result.primary_symbol,result.primary_exchange)==(symbol,exchange)
