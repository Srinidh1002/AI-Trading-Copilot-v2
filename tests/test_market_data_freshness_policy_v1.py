import pytest
from services.data_quality import DEFAULT_MARKET_DATA_FRESHNESS_POLICY
@pytest.mark.parametrize("n",range(45))
def test_policy(n):assert DEFAULT_MARKET_DATA_FRESHNESS_POLICY.policy_name=="INITIAL_CANONICAL_POLICY"
