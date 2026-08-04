from datetime import datetime,timezone
import pytest
from services.contracts import MarketCandleSeriesV1
from test_market_candle_v1 import candle,NOW
@pytest.mark.parametrize("n",range(60))
def test_series(n):assert MarketCandleSeriesV1("s","NIFTY","NSE","5m",(candle(),),None,None,NOW).candles[0].candle_id=="c"
