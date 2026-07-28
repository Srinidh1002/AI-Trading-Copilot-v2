from datetime import date,datetime,timedelta,timezone
from dataclasses import FrozenInstanceError
import pytest
from services.contracts import PaperExecutionAuthorizationV1
N=datetime(2026,7,27,10,tzinfo=timezone.utc)
def auth(**c):
 v=dict(authorization_id="a",created_at=N,authorized_at=N,valid_from=N,valid_until=N+timedelta(minutes=5),authorization_status="APPROVED",authorized_by="user",approval_reason="approve",idempotency_key="key",execution_request_id="request",paper_candidate_id="candidate",canonical_risk_result_id="risk",sizing_result_id="size",trade_plan_id="plan",decision_id="decision",snapshot_id="snapshot",underlying_symbol="NIFTY",exchange="NSE",action="BUY",option_type="CALL",position_side="LONG",trading_symbol="OPT",expiry_date=date(2026,7,30),strike=25000.,quantity=100,lots=2,lot_size=50,session_id="session",session_date=N.date(),session_exchange="NSE");v.update(c);return PaperExecutionAuthorizationV1(**v)
def test_frozen_slots_and_json():
 x=auth();assert not hasattr(x,"__dict__") and x.to_json()==auth().to_json()
 with pytest.raises(FrozenInstanceError):x.authorization_id="x"
@pytest.mark.parametrize("symbol,exchange,action,kind",[("NIFTY","NSE","BUY","CALL"),("NIFTY","NSE","SELL","PUT"),("SENSEX","BSE","BUY","CALL"),("SENSEX","BSE","SELL","PUT")])
def test_long_premium_identities(symbol,exchange,action,kind):assert auth(underlying_symbol=symbol,exchange=exchange,session_exchange=exchange,action=action,option_type=kind).live_execution_eligible is False
@pytest.mark.parametrize("field,value",[("authorization_id",""),("authorized_by",""),("approval_reason",""),("idempotency_key",""),("execution_request_id",""),("paper_candidate_id",""),("canonical_risk_result_id",""),("sizing_result_id",""),("trade_plan_id",""),("decision_id",""),("snapshot_id",""),("session_id","")])
def test_empty_fields(field,value):
 with pytest.raises(ValueError):auth(**{field:value})
@pytest.mark.parametrize("field,value",[("created_at",datetime(2026,7,27)),("authorized_at",datetime(2026,7,27)),("valid_from",datetime(2026,7,27)),("valid_until",datetime(2026,7,27)),("authorization_mode","AUTO"),("execution_mode","LIVE"),("live_execution_eligible",True),("authorization_status","BAD"),("underlying_symbol","OTHER"),("session_exchange","BSE"),("action","WAIT"),("option_type","PUT"),("position_side","SHORT"),("strike",0),("quantity",0),("lots",0),("lot_size",0)])
def test_invalid_controls(field,value):
 with pytest.raises(ValueError):auth(**{field:value})
@pytest.mark.parametrize("changes",[{"quantity":50},{"valid_until":N},{"authorized_at":N-timedelta(seconds=1)},{"valid_from":N+timedelta(seconds=1)},{"authorization_status":"REVOKED"},{"authorization_status":"EXPIRED"},{"authorization_status":"BLOCKED"}])
def test_invalid_arithmetic_times_and_statuses(changes):
 with pytest.raises(ValueError):auth(**changes)
@pytest.mark.parametrize("status",["REVOKED","EXPIRED","BLOCKED"])
def test_nonapproved_requires_reason(status):assert auth(authorization_status=status,blockers=("reason",)).blockers==("reason",)
def test_semantics_exclude_generated_fields():assert auth(authorization_id="1").semantic_dict()==auth(authorization_id="2",created_at=N-timedelta(seconds=1)).semantic_dict()
