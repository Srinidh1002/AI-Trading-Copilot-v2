from datetime import datetime,timedelta,timezone
from dataclasses import FrozenInstanceError
import pytest
from services.contracts import PaperAuthorizationResultV1
N=datetime(2026,7,27,10,tzinfo=timezone.utc)
def result(**c):
 v=dict(authorization_result_id="result",created_at=N,authorization_status="AUTHORIZED",execution_request_id="request",idempotency_key="key",validated_at=N,manual_authorization_valid=True,paper_execution_eligible=True,authorization_id="auth",paper_candidate_id="candidate",canonical_risk_result_id="risk",sizing_result_id="size",trade_plan_id="plan",session_id="session",underlying_symbol="NIFTY",exchange="NSE",action="BUY",option_type="CALL",position_side="LONG",trading_symbol="OPT",quantity=100,lots=2,authorization_valid_from=N,authorization_valid_until=N+timedelta(minutes=1));v.update(c);return PaperAuthorizationResultV1(**v)
def test_frozen_slots_and_determinism():
 x=result();assert not hasattr(x,"__dict__") and x.to_json()==result().to_json()
 with pytest.raises(FrozenInstanceError):x.paper_execution_eligible=False
@pytest.mark.parametrize("field",["authorization_result_id","execution_request_id","idempotency_key"])
def test_ids(field):
 with pytest.raises(ValueError):result(**{field:""})
@pytest.mark.parametrize("field,value",[("created_at",datetime(2026,7,27)),("validated_at",datetime(2026,7,27)),("execution_mode","LIVE"),("live_execution_eligible",True),("authorization_status","BAD"),("manual_authorization_valid",False),("paper_execution_eligible",False),("action","SELL"),("option_type","PUT"),("position_side","SHORT"),("authorization_id",None),("session_id",None)])
def test_invalid_authorized_result(field,value):
 with pytest.raises(ValueError):result(**{field:value})
@pytest.mark.parametrize("status",["NOT_APPROVED","EXPIRED","REVOKED","SESSION_INVALID","IDENTITY_MISMATCH","IDEMPOTENCY_MISMATCH","BLOCKED","FAILED"])
def test_non_authorized_requires_blocking(status):
 with pytest.raises(ValueError):result(authorization_status=status,manual_authorization_valid=False,paper_execution_eligible=False,blockers=())
@pytest.mark.parametrize("status",["NOT_APPROVED","EXPIRED","REVOKED","SESSION_INVALID","IDENTITY_MISMATCH","IDEMPOTENCY_MISMATCH","BLOCKED","FAILED"])
def test_non_authorized_is_honest(status):assert result(authorization_status=status,manual_authorization_valid=False,paper_execution_eligible=False,blockers=("blocked",),authorization_id="auth" if status=="REVOKED" else None,authorization_valid_until=N+timedelta(minutes=1) if status=="EXPIRED" else None).paper_execution_eligible is False
@pytest.mark.parametrize("field",["authorization_id","paper_candidate_id","canonical_risk_result_id","sizing_result_id","trade_plan_id","session_id","underlying_symbol","exchange","action","option_type","position_side","trading_symbol","authorization_valid_from","authorization_valid_until"])
def test_authorized_linkage_required(field):
 with pytest.raises(ValueError):result(**{field:None})
def test_semantics_exclude_generated_values():assert result(authorization_result_id="1").semantic_dict()==result(authorization_result_id="2",created_at=N+timedelta(seconds=1)).semantic_dict()
