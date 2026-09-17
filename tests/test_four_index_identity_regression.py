import pytest
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES,SUPPORTED_MARKET_SYMBOLS,normalize_market_identity,is_supported_market_identity
@pytest.mark.parametrize("pair",[("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")])
def test_exact_identity_pair(pair):assert pair in SUPPORTED_MARKET_IDENTITIES and is_supported_market_identity(*pair)
def test_exact_ordering():assert SUPPORTED_MARKET_SYMBOLS==("NIFTY","BANKNIFTY","FINNIFTY","SENSEX")
@pytest.mark.parametrize("symbol,exchange",[("NIFTY","BSE"),("BANKNIFTY","BSE"),("FINNIFTY","BSE"),("SENSEX","NSE"),("OTHER","NSE")])
def test_mismatches_reject(symbol,exchange):assert normalize_market_identity(symbol,exchange) is None
@pytest.mark.parametrize("index",range(30))
def test_regression_identity_is_deterministic(index):assert normalize_market_identity("BANK NIFTY","NSE")==("BANKNIFTY","NSE")
