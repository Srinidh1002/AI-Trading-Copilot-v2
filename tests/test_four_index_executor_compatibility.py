import pytest
from test_paper_authorization_validator import request,authorization,session,N
from services.paper import execute_paper_order,validate_paper_execution_authorization,InMemoryPaperExecutionIdempotencyStore
@pytest.mark.parametrize("symbol,exchange,action,kind",[("NIFTY","NSE","BUY","CALL"),("NIFTY","NSE","SELL","PUT"),("BANKNIFTY","NSE","BUY","CALL"),("BANKNIFTY","NSE","SELL","PUT"),("FINNIFTY","NSE","BUY","CALL"),("FINNIFTY","NSE","SELL","PUT"),("SENSEX","BSE","BUY","CALL"),("SENSEX","BSE","SELL","PUT")])
def test_executor_four_index(symbol,exchange,action,kind):
 r=request(underlying_symbol=symbol,exchange=exchange,action=action,option_type=kind);a=validate_paper_execution_authorization(execution_request=r,authorization=authorization(r,session_exchange=exchange),session_validation=session(exchange=exchange,symbol=symbol),clock=lambda:N,result_id_factory=lambda:"a");assert execute_paper_order(execution_request=r,authorization_result=a,clock=lambda:N,execution_result_id_factory=lambda:"r").execution_status=="FILLED"
@pytest.mark.parametrize("index",range(32))
def test_executor_duplicate_no_second_fill(index):
 r=request(idempotency_key=f"k{index}");a=validate_paper_execution_authorization(execution_request=r,authorization=authorization(r),session_validation=session(),clock=lambda:N,result_id_factory=lambda:"a");s=InMemoryPaperExecutionIdempotencyStore();execute_paper_order(execution_request=r,authorization_result=a,idempotency_store=s,clock=lambda:N,execution_result_id_factory=lambda:"1");assert execute_paper_order(execution_request=r,authorization_result=a,idempotency_store=s,clock=lambda:N,execution_result_id_factory=lambda:"2").execution_status=="DUPLICATE"
