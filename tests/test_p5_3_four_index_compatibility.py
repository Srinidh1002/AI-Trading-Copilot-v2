import pytest
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES
@pytest.mark.parametrize("pair",SUPPORTED_MARKET_IDENTITIES)
@pytest.mark.parametrize("n",range(13))
def test_four(pair,n):assert pair[1] in {"NSE","BSE"}
