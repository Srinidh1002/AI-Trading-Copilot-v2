import pytest
from services.core.market_identity import is_supported_market_identity
@pytest.mark.parametrize("symbol,exchange",[("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")])
def test_candidate_identity_precondition(symbol,exchange):assert is_supported_market_identity(symbol,exchange)
@pytest.mark.parametrize("index",range(21))
def test_candidate_invalid_exchange_is_blocked_precondition(index):assert not is_supported_market_identity("BANKNIFTY","BSE")
