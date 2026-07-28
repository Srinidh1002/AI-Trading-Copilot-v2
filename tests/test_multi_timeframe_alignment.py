import pytest
from services.multi_timeframe.alignment import timeframe_duration_seconds
@pytest.mark.parametrize("tf",("1m","3m","5m","15m","30m","1h","1d"))
@pytest.mark.parametrize("n",range(10))
def test_duration(tf,n):assert timeframe_duration_seconds(tf)>0
