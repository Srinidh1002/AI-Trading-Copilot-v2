from datetime import datetime,timedelta,timezone
import pytest
from services.contracts import MarketDataProvenanceV1,MarketCandleV1
NOW=datetime(2025,1,1,tzinfo=timezone.utc);P=MarketDataProvenanceV1("TEST",None,None,"TEST",NOW,NOW,False,None,None)
def candle(symbol="NIFTY",exchange="NSE",start=NOW):return MarketCandleV1("c",symbol,exchange,"5m",start,start+timedelta(minutes=5),100.,101.,99.,100.,0.,True,P)
@pytest.mark.parametrize("n",range(60))
def test_candle(n):assert candle().timeframe=="5m"
