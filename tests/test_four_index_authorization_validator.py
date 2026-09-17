import pytest
from test_paper_authorization_validator import request,authorization,session,N
from services.paper import validate_paper_execution_authorization
@pytest.mark.parametrize("symbol,exchange,action,kind",[("NIFTY","NSE","BUY","CALL"),("NIFTY","NSE","SELL","PUT"),("BANKNIFTY","NSE","BUY","CALL"),("BANKNIFTY","NSE","SELL","PUT"),("FINNIFTY","NSE","BUY","CALL"),("FINNIFTY","NSE","SELL","PUT"),("SENSEX","BSE","BUY","CALL"),("SENSEX","BSE","SELL","PUT")])
def test_validator_four_index(symbol,exchange,action,kind):
 r=request(underlying_symbol=symbol,exchange=exchange,action=action,option_type=kind);a=authorization(r,session_exchange=exchange);assert validate_paper_execution_authorization(execution_request=r,authorization=a,session_validation=session(exchange=exchange,symbol=symbol),clock=lambda:N,result_id_factory=lambda:"z").authorization_status=="AUTHORIZED"
@pytest.mark.parametrize("index",range(27))
def test_missing_session_stays_invalid(index):
 assert validate_paper_execution_authorization(execution_request=request(),authorization=authorization(),clock=lambda:N,result_id_factory=lambda:"z").authorization_status=="SESSION_INVALID"
