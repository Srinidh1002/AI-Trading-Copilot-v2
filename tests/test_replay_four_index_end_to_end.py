import pytest
from test_paper_authorization_validator import request,authorization,session,N
from services.core.market_identity import normalize_market_identity
from services.paper import validate_paper_execution_authorization,execute_paper_order,InMemoryPaperExecutionIdempotencyStore
PAIRS=[("NIFTY","NSE","BUY","CALL"),("NIFTY","NSE","SELL","PUT"),("BANKNIFTY","NSE","BUY","CALL"),("BANKNIFTY","NSE","SELL","PUT"),("FINNIFTY","NSE","BUY","CALL"),("FINNIFTY","NSE","SELL","PUT"),("SENSEX","BSE","BUY","CALL"),("SENSEX","BSE","SELL","PUT")]
@pytest.mark.parametrize("symbol,exchange,action,kind",PAIRS)
def test_replay_full_authorized_fill_and_duplicate(symbol,exchange,action,kind):
 r=request(underlying_symbol=symbol,exchange=exchange,action=action,option_type=kind,idempotency_key=f"{symbol}-{action}");a=authorization(r,session_exchange=exchange);v=validate_paper_execution_authorization(execution_request=r,authorization=a,session_validation=session(exchange=exchange,symbol=symbol),clock=lambda:N,result_id_factory=lambda:"a");s=InMemoryPaperExecutionIdempotencyStore();first=execute_paper_order(execution_request=r,authorization_result=v,idempotency_store=s,clock=lambda:N,execution_result_id_factory=lambda:"one");second=execute_paper_order(execution_request=r,authorization_result=v,idempotency_store=s,clock=lambda:N,execution_result_id_factory=lambda:"two");assert normalize_market_identity(symbol,exchange)==(symbol,exchange) and first.execution_status=="FILLED" and second.execution_status=="DUPLICATE" and first.live_execution_eligible is False
@pytest.mark.parametrize("index",range(40))
def test_replay_blocked_authorization_does_not_claim(index):
 r=request(idempotency_key=f"blocked-{index}");a=validate_paper_execution_authorization(execution_request=r,authorization=None,session_validation=session(),clock=lambda:N,result_id_factory=lambda:"a");s=InMemoryPaperExecutionIdempotencyStore();assert execute_paper_order(execution_request=r,authorization_result=a,idempotency_store=s,clock=lambda:N,execution_result_id_factory=lambda:"r").execution_status=="BLOCKED" and s.get(r.idempotency_key) is None
