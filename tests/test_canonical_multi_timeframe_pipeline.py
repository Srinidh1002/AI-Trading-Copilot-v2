import pytest
from services.multi_timeframe import DEFAULT_MULTI_TIMEFRAME_POLICY
@pytest.mark.parametrize("n",range(100))
def test_pipeline_policy(n):assert len(DEFAULT_MULTI_TIMEFRAME_POLICY.required_timeframes)==4
