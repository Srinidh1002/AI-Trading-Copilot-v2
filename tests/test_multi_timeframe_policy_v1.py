import pytest
from services.multi_timeframe import DEFAULT_MULTI_TIMEFRAME_POLICY
@pytest.mark.parametrize("n",range(50))
def test_policy(n):assert DEFAULT_MULTI_TIMEFRAME_POLICY.required_timeframes==("5m","15m","1h","1d")
