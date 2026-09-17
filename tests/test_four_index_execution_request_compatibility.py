import pytest
from test_paper_authorization_validator import request
@pytest.mark.parametrize("symbol,exchange,action,kind",[("NIFTY","NSE","BUY","CALL"),("NIFTY","NSE","SELL","PUT"),("BANKNIFTY","NSE","BUY","CALL"),("BANKNIFTY","NSE","SELL","PUT"),("FINNIFTY","NSE","BUY","CALL"),("FINNIFTY","NSE","SELL","PUT"),("SENSEX","BSE","BUY","CALL"),("SENSEX","BSE","SELL","PUT")])
def test_request_four_index(symbol,exchange,action,kind):assert request(underlying_symbol=symbol,exchange=exchange,action=action,option_type=kind).live_execution_eligible is False
@pytest.mark.parametrize("index",range(22))
def test_request_mismatch_rejected(index):
 with pytest.raises(ValueError):request(underlying_symbol="BANKNIFTY",exchange="BSE")
