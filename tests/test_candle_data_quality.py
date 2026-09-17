import pytest
from services.data_quality import evaluate_market_candle_quality,evaluate_market_candle_series_quality
from test_market_candle_v1 import candle,NOW
from services.contracts import MarketCandleSeriesV1
@pytest.mark.parametrize("n",range(95))
def test_candle_quality(n):
 value=candle();assert evaluate_market_candle_quality(value,clock=lambda:value.end_at).quality_status=="VALID"
