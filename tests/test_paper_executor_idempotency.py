import pytest
from test_paper_authorization_validator import request,authorization,session,N
from services.paper import execute_paper_order,InMemoryPaperExecutionIdempotencyStore
from services.paper.authorization import validate_paper_execution_authorization
@pytest.mark.parametrize("index",range(30))
def test_duplicate_key_returns_nonfilled_duplicate(index):
 r=request(idempotency_key=f"key-{index}");a=validate_paper_execution_authorization(execution_request=r,authorization=authorization(r),session_validation=session(),clock=lambda:N,result_id_factory=lambda:"auth") ;s=InMemoryPaperExecutionIdempotencyStore()
 assert execute_paper_order(execution_request=r,authorization_result=a,idempotency_store=s,clock=lambda:N,execution_result_id_factory=lambda:"one").execution_status=="FILLED"
 second=execute_paper_order(execution_request=r,authorization_result=a,idempotency_store=s,clock=lambda:N,execution_result_id_factory=lambda:"two")
 assert second.execution_status=="DUPLICATE" and second.fill_price is None
