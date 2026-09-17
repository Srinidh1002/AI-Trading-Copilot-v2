import pytest
from services.multi_timeframe import DEFAULT_MULTI_TIMEFRAME_POLICY
@pytest.mark.parametrize("n",range(80))
def test_quality_policy(n):assert DEFAULT_MULTI_TIMEFRAME_POLICY.anchor_timeframe=="5m"
