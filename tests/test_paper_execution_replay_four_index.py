import pytest
from test_paper_execution_replay import canonical,observations,NOW
from services.paper import replay_canonical_paper_execution
CASES=(("NIFTY","NSE","BUY","CALL"),("NIFTY","NSE","SELL","PUT"),("BANKNIFTY","NSE","BUY","CALL"),("BANKNIFTY","NSE","SELL","PUT"),("FINNIFTY","NSE","BUY","CALL"),("FINNIFTY","NSE","SELL","PUT"),("SENSEX","BSE","BUY","CALL"),("SENSEX","BSE","SELL","PUT"))
@pytest.mark.parametrize("symbol,exchange,action,kind",CASES)
@pytest.mark.parametrize("repeat",range(5))
def test_four_index_replay(symbol,exchange,action,kind,repeat):
 c=canonical(underlying_symbol=symbol,exchange=exchange,action=action,option_type=kind,trading_symbol=f"{symbol}{kind}");assert replay_canonical_paper_execution(canonical_execution_result=c,observations=observations(c),clock=lambda:NOW).replay_status=="MATCHED"
