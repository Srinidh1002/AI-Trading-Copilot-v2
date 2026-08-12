import pytest

from services.broker.angel_endpoint_policies import (
    CONSERVATIVE_MARKET_QUOTE_POLICY,
    CONSERVATIVE_HISTORICAL_POLICY,
    DOCUMENTED_ENDPOINT_POLICIES,
    HISTORICAL_MAX_LOOKBACK_DAYS,
    validate_historical_timeframe_config,
)


def test_conservative_market_quote_policy_uses_stricter_documented_limit():
    assert CONSERVATIVE_MARKET_QUOTE_POLICY.requests_per_second == 1
from services.market.live_multi_timeframe_data import TIMEFRAME_CONFIG


def test_documented_endpoint_limits_and_conservative_historical_headroom():
    assert DOCUMENTED_ENDPOINT_POLICIES["historical-data"].requests_per_second == 3
    assert DOCUMENTED_ENDPOINT_POLICIES["historical-data"].requests_per_minute == 150
    assert DOCUMENTED_ENDPOINT_POLICIES["historical-data"].requests_per_hour == 5000
    assert (DOCUMENTED_ENDPOINT_POLICIES["market-quote"].requests_per_second, DOCUMENTED_ENDPOINT_POLICIES["market-quote"].requests_per_minute, DOCUMENTED_ENDPOINT_POLICIES["market-quote"].requests_per_hour) == (10, 500, 5000)
    assert (DOCUMENTED_ENDPOINT_POLICIES["ltp"].requests_per_second, DOCUMENTED_ENDPOINT_POLICIES["ltp"].requests_per_minute, DOCUMENTED_ENDPOINT_POLICIES["ltp"].requests_per_hour) == (10, 500, 5000)
    assert (DOCUMENTED_ENDPOINT_POLICIES["option-greeks"].requests_per_second, DOCUMENTED_ENDPOINT_POLICIES["option-greeks"].requests_per_minute, DOCUMENTED_ENDPOINT_POLICIES["option-greeks"].requests_per_hour) == (1, None, None)
    assert (CONSERVATIVE_HISTORICAL_POLICY.requests_per_second, CONSERVATIVE_HISTORICAL_POLICY.requests_per_minute, CONSERVATIVE_HISTORICAL_POLICY.requests_per_hour) == (1, 120, 4000)
    documented = DOCUMENTED_ENDPOINT_POLICIES["historical-data"]
    assert CONSERVATIVE_HISTORICAL_POLICY.requests_per_second <= documented.requests_per_second
    assert CONSERVATIVE_HISTORICAL_POLICY.requests_per_minute <= documented.requests_per_minute
    assert CONSERVATIVE_HISTORICAL_POLICY.requests_per_hour <= documented.requests_per_hour


def test_historical_maximums_and_current_timeframes_are_validated():
    assert HISTORICAL_MAX_LOOKBACK_DAYS == {"ONE_MINUTE": 30, "THREE_MINUTE": 60, "FIVE_MINUTE": 100, "TEN_MINUTE": 100, "FIFTEEN_MINUTE": 200, "THIRTY_MINUTE": 200, "ONE_HOUR": 400, "ONE_DAY": 2000}
    validate_historical_timeframe_config(TIMEFRAME_CONFIG)
    with pytest.raises(ValueError, match="maximum"):
        validate_historical_timeframe_config({"bad": {"interval": "FIVE_MINUTE", "lookback_days": 101}})
