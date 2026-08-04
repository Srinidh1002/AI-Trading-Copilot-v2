from datetime import datetime,timezone
import pytest
from services.contracts import MarketDataProvenanceV1,MarketQuoteV1
NOW=datetime(2025,1,1,tzinfo=timezone.utc); P=MarketDataProvenanceV1("TEST",None,None,"TEST",NOW,NOW,False,None,None)
def quote(symbol="NIFTY",exchange="NSE"):return MarketQuoteV1("q",symbol,exchange,NOW,NOW,100.,99.,100.,101.,99.,0.,None,None,P)
@pytest.mark.parametrize("n",range(60))
def test_quote(n):assert quote().last_price==100
