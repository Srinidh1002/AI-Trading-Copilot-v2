import pytest
from test_paper_execution_result_v1 import filled
@pytest.mark.parametrize("symbol,exchange,action,kind",[("NIFTY","NSE","BUY","CALL"),("NIFTY","NSE","SELL","PUT"),("BANKNIFTY","NSE","BUY","CALL"),("BANKNIFTY","NSE","SELL","PUT"),("FINNIFTY","NSE","BUY","CALL"),("FINNIFTY","NSE","SELL","PUT"),("SENSEX","BSE","BUY","CALL"),("SENSEX","BSE","SELL","PUT")])
def test_result_four_index(symbol,exchange,action,kind):assert filled(underlying_symbol=symbol,exchange=exchange,action=action,option_type=kind).execution_status=="FILLED"
@pytest.mark.parametrize("index",range(22))
def test_result_mismatch_rejected(index):
 with pytest.raises(ValueError):filled(underlying_symbol="BANKNIFTY",exchange="BSE")
