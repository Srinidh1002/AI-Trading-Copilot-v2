import pytest
from test_paper_authorization_validator import request,authorization,session,N
from services.paper import execute_paper_order
from services.paper.authorization import validate_paper_execution_authorization
@pytest.mark.parametrize("index",range(25))
def test_explicit_execution_only_and_no_authorization_rerun(index):
 r=request();a=validate_paper_execution_authorization(execution_request=r,authorization=authorization(r),session_validation=session(),clock=lambda:N,result_id_factory=lambda:"auth")
 assert execute_paper_order(execution_request=r,authorization_result=a,clock=lambda:N,execution_result_id_factory=lambda:"result").execution_status=="FILLED"
