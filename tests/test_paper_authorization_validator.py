from datetime import date,datetime,timedelta,timezone
from types import SimpleNamespace
import pytest
from services.contracts import PaperExecutionRequestV1,PaperExecutionAuthorizationV1
from services.paper import validate_paper_execution_authorization
N=datetime(2026,7,27,10,tzinfo=timezone.utc)
def request(**c):
 v=dict(execution_request_id="request",created_at=N,authorization_id="auth",idempotency_key="key",snapshot_id="snapshot",analysis_id="analysis",decision_id="decision",trade_plan_result_id="plan-result",trade_plan_id="plan",sizing_result_id="size",canonical_risk_result_id="risk",paper_candidate_id="candidate",underlying_symbol="NIFTY",exchange="NSE",action="BUY",option_type="CALL",position_side="LONG",trading_symbol="OPT",expiry_date=date(2026,7,30),strike=25000.,lot_size=50,quantity=100,lots=2,entry_reference_price=100.,stop_loss_price=90.,target_price=120.,capital_required=10000.,maximum_loss=1000.,reward_risk_ratio=2.,valid_from=N,valid_until=N+timedelta(minutes=5));v.update(c);return PaperExecutionRequestV1(**v)
def authorization(r=None,**c):
 r=r or request();v=dict(authorization_id="auth",created_at=N,authorized_at=N,valid_from=N,valid_until=N+timedelta(minutes=5),authorization_status="APPROVED",authorized_by="user",approval_reason="ok",idempotency_key=r.idempotency_key,execution_request_id=r.execution_request_id,paper_candidate_id=r.paper_candidate_id,canonical_risk_result_id=r.canonical_risk_result_id,sizing_result_id=r.sizing_result_id,trade_plan_id=r.trade_plan_id,decision_id=r.decision_id,snapshot_id=r.snapshot_id,underlying_symbol=r.underlying_symbol,exchange=r.exchange,action=r.action,option_type=r.option_type,position_side=r.position_side,trading_symbol=r.trading_symbol,expiry_date=r.expiry_date,strike=r.strike,quantity=r.quantity,lots=r.lots,lot_size=r.lot_size,session_id="session",session_date=N.date(),session_exchange=r.exchange);v.update(c);return PaperExecutionAuthorizationV1(**v)
def session(**c):
 v=dict(validation_id="session",trading_date=N.date(),exchange="NSE",symbol="NIFTY",paper_execution_allowed=True,blockers=(),stale=False,future_timestamp=False);v.update(c);return SimpleNamespace(**v)
def run(r=None,a=None,s=None,now=N):return validate_paper_execution_authorization(execution_request=r or request(),authorization=authorization(r) if a is None else a,session_validation=session() if s is None else s,clock=lambda:now,result_id_factory=lambda:"result")
@pytest.mark.parametrize("symbol,exchange,action,kind",[("NIFTY","NSE","BUY","CALL"),("NIFTY","NSE","SELL","PUT"),("SENSEX","BSE","BUY","CALL"),("SENSEX","BSE","SELL","PUT")])
def test_supported_authorizations(symbol,exchange,action,kind):
 r=request(underlying_symbol=symbol,exchange=exchange,action=action,option_type=kind);assert run(r,authorization(r,session_exchange=exchange),session(exchange=exchange,symbol=symbol)).authorization_status=="AUTHORIZED"
def test_missing_authorization_is_not_approved():
 value=validate_paper_execution_authorization(execution_request=request(),authorization=None,session_validation=session(),clock=lambda:N,result_id_factory=lambda:"result")
 assert value.authorization_status=="NOT_APPROVED" and value.paper_execution_eligible is False
@pytest.mark.parametrize("status",["REVOKED","EXPIRED","BLOCKED"])
def test_declared_states(status):assert run(a=authorization(authorization_status=status,blockers=("state",))).authorization_status==status
@pytest.mark.parametrize("now,status",[(N-timedelta(seconds=1),"NOT_APPROVED"),(N,"AUTHORIZED"),(N+timedelta(minutes=4),"AUTHORIZED"),(N+timedelta(minutes=5),"EXPIRED"),(N+timedelta(minutes=6),"EXPIRED")])
def test_time_window(now,status):assert run(now=now).authorization_status==status
@pytest.mark.parametrize("field",["execution_request_id","paper_candidate_id","canonical_risk_result_id","sizing_result_id","trade_plan_id","decision_id","snapshot_id","trading_symbol","expiry_date","strike"])
def test_exact_identity_binding(field):
 r=request(); value="other" if isinstance(getattr(r,field),str) else 1 if isinstance(getattr(r,field),(int,float)) else date(2026,8,1);a=authorization(r,**{field:value})
 assert run(r,a).authorization_status=="IDENTITY_MISMATCH"
def test_idempotency_mismatch():assert run(a=authorization(idempotency_key="other")).authorization_status=="IDEMPOTENCY_MISMATCH"
@pytest.mark.parametrize("changes",[{}, {"paper_execution_allowed":False},{"blockers":("closed",)},{"validation_id":"other"},{"trading_date":date(2026,7,28)},{"exchange":"BSE"},{"symbol":"SENSEX"},{"stale":True},{"future_timestamp":True}])
def test_session_evidence_is_authoritative(changes):
 status=run(s=session(**changes)).authorization_status;assert status==("AUTHORIZED" if not changes else "SESSION_INVALID")
@pytest.mark.parametrize("index",range(39))
def test_authorized_result_is_deterministic_and_nonlive(index):
 value=run();assert value.authorization_result_id=="result" and value.live_execution_eligible is False and value.paper_execution_eligible is True
