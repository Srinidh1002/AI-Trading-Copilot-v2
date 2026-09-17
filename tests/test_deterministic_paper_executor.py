import pytest
from test_paper_authorization_validator import request,authorization,session,N
from services.paper import execute_paper_order
from services.paper.authorization import validate_paper_execution_authorization
def approved(r=None):
 r=r or request();return r,validate_paper_execution_authorization(execution_request=r,authorization=authorization(r),session_validation=session(exchange=r.exchange,symbol=r.underlying_symbol),clock=lambda:N,result_id_factory=lambda:"auth-result")
@pytest.mark.parametrize("index",range(70))
def test_deterministic_full_fill(index):
 r,a=approved();v=execute_paper_order(execution_request=r,authorization_result=a,clock=lambda:N,execution_result_id_factory=lambda:"result")
 assert (v.execution_status,v.filled_quantity,v.filled_lots,v.fill_price,v.capital_used,v.realized_maximum_loss,v.submitted_at,v.filled_at,v.live_execution_eligible)==("FILLED",r.quantity,r.lots,r.entry_reference_price,r.entry_reference_price*r.quantity,(r.entry_reference_price-r.stop_loss_price)*r.quantity,N,N,False)
