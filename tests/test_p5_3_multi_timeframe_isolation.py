import pytest
@pytest.mark.parametrize("n",range(40))
def test_isolation(n):
 import services.multi_timeframe
 assert "yfinance" not in services.multi_timeframe.__dict__
