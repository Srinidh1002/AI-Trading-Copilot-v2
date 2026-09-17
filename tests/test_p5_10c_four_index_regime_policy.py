import pytest
from services.contracts.market_regime_policy_v1 import DEFAULT_MARKET_REGIME_POLICY
@pytest.mark.parametrize("identity",(("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")))
def test_all_four_identities_have_policy_mappings(identity):assert identity in DEFAULT_MARKET_REGIME_POLICY.required_components_by_identity
