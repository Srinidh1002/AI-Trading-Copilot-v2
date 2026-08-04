import pytest
from test_paper_order_state_v1 import filled
@pytest.mark.parametrize("symbol,exchange,action,kind",[("NIFTY","NSE","BUY","CALL"),("NIFTY","NSE","SELL","PUT"),("BANKNIFTY","NSE","BUY","CALL"),("BANKNIFTY","NSE","SELL","PUT"),("FINNIFTY","NSE","BUY","CALL"),("FINNIFTY","NSE","SELL","PUT"),("SENSEX","BSE","BUY","CALL"),("SENSEX","BSE","SELL","PUT")])
def test_order_state_long_directions(symbol,exchange,action,kind):assert filled(action=action,option_type=kind).order_status=="FILLED"
@pytest.mark.parametrize("index",range(22))
def test_order_state_short_rejected(index):
 with pytest.raises(ValueError):filled(position_side="SHORT")
