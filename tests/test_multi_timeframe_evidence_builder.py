import pytest
from test_market_candle_v1 import candle,NOW
from services.contracts import MarketCandleSeriesV1
from services.multi_timeframe import build_timeframe_evidence
@pytest.mark.parametrize("n",range(70))
def test_builder(n):
 s=MarketCandleSeriesV1("s","NIFTY","NSE","5m",(candle(),),None,None,NOW);assert build_timeframe_evidence(s,clock=lambda:candle().end_at).timeframe=="5m"
