import pytest
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES,normalize_market_identity
from services.core.market_universe import CANONICAL_MARKET_IDENTITIES
@pytest.mark.parametrize("pair",SUPPORTED_MARKET_IDENTITIES)
@pytest.mark.parametrize("check",range(13))
def test_existing_identity_behavior_matches_canonical_universe(pair,check):assert normalize_market_identity(*pair)==pair and pair in CANONICAL_MARKET_IDENTITIES
