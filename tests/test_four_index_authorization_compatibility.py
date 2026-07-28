import pytest
from test_paper_authorization_validator import request,authorization
@pytest.mark.parametrize("symbol,exchange,action,kind",[("NIFTY","NSE","BUY","CALL"),("NIFTY","NSE","SELL","PUT"),("BANKNIFTY","NSE","BUY","CALL"),("BANKNIFTY","NSE","SELL","PUT"),("FINNIFTY","NSE","BUY","CALL"),("FINNIFTY","NSE","SELL","PUT"),("SENSEX","BSE","BUY","CALL"),("SENSEX","BSE","SELL","PUT")])
def test_authorization_four_index(symbol,exchange,action,kind):
 r=request(underlying_symbol=symbol,exchange=exchange,action=action,option_type=kind);assert authorization(r,session_exchange=exchange).authorization_status=="APPROVED"
@pytest.mark.parametrize("index",range(22))
def test_authorization_mismatch_rejected(index):
 with pytest.raises(ValueError):authorization(request(),underlying_symbol="FINNIFTY",exchange="BSE",session_exchange="BSE")
