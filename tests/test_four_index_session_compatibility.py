import pytest
from services.market_session.identity import normalize_market_identity
@pytest.mark.parametrize("symbol,exchange",[("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")])
def test_session_identity_preserved(symbol,exchange):
 value=normalize_market_identity(symbol,exchange);assert value and (value.canonical_symbol,value.exchange)==(symbol,exchange)
@pytest.mark.parametrize("index",range(21))
def test_session_mismatch_rejected(index):assert normalize_market_identity("FINNIFTY","BSE") is None
