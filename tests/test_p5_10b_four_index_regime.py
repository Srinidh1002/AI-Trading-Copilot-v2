import pytest
from services.core.market_identity import normalize_market_identity
@pytest.mark.parametrize("s,e",(("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")))
def test_canonical_regime_identity(s,e):assert normalize_market_identity(s,e)==(s,e)
