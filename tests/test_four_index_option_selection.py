import pytest
from services.core.market_identity import normalize_market_identity
@pytest.mark.parametrize("symbol,exchange,action,kind",[("NIFTY","NSE","BUY","CALL"),("NIFTY","NSE","SELL","PUT"),("BANKNIFTY","NSE","BUY","CALL"),("BANKNIFTY","NSE","SELL","PUT"),("FINNIFTY","NSE","BUY","CALL"),("FINNIFTY","NSE","SELL","PUT"),("SENSEX","BSE","BUY","CALL"),("SENSEX","BSE","SELL","PUT")])
def test_selection_identity_inputs_are_supported(symbol,exchange,action,kind):assert normalize_market_identity(symbol,exchange)==(symbol,exchange) and (action,kind) in {("BUY","CALL"),("SELL","PUT")}
@pytest.mark.parametrize("index",range(22))
def test_selection_invalid_pair_has_no_identity(index):assert normalize_market_identity("FINNIFTY","BSE") is None
