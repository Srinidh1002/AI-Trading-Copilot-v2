from dataclasses import FrozenInstanceError
from datetime import datetime,timedelta,timezone
import pytest
from services.contracts import PaperOrderStateV1
NOW=datetime(2026,7,27,10,tzinfo=timezone.utc)
def state(**c):
 v=dict(paper_order_id="order",created_at=NOW,updated_at=NOW,order_status="CREATED",execution_request_id="request",idempotency_key="key",underlying_symbol="NIFTY",exchange="NSE");v.update(c);return PaperOrderStateV1(**v)
def submitted(**c):
 v=dict(order_status="SUBMITTED",authorization_id="auth",paper_candidate_id="candidate",canonical_risk_result_id="risk",trading_symbol="OPT",action="BUY",option_type="CALL",position_side="LONG",quantity=100,lots=2,reference_price=100.);v.update(c);return state(**v)
def filled(**c):
 v=dict(order_status="FILLED",authorization_id="auth",execution_result_id="result",paper_candidate_id="candidate",canonical_risk_result_id="risk",trading_symbol="OPT",action="BUY",option_type="CALL",position_side="LONG",quantity=100,lots=2,reference_price=100.,fill_price=100.);v.update(c);return state(**v)
def test_frozen_slots_and_determinism():
 value=state();assert not hasattr(value,"__dict__") and value.to_json()==state().to_json()
 with pytest.raises(FrozenInstanceError):value.order_status="FAILED"
@pytest.mark.parametrize("field",["paper_order_id","execution_request_id","idempotency_key"])
def test_required_ids(field):
 with pytest.raises(ValueError):state(**{field:""})
@pytest.mark.parametrize("field,value",[("created_at",datetime(2026,7,27)),("updated_at",datetime(2026,7,27)),("updated_at",NOW-timedelta(seconds=1)),("schema_version","bad"),("execution_mode","LIVE"),("live_execution_eligible",True),("order_status","BAD"),("blockers",("",)),("warnings",("",))])
def test_control_and_time_validation(field,value):
 with pytest.raises(ValueError):state(**{field:value})
@pytest.mark.parametrize("status",["REJECTED","BLOCKED","FAILED"])
def test_terminal_rejection_requires_blocker(status):
 with pytest.raises(ValueError):state(order_status=status)
@pytest.mark.parametrize("status",["REJECTED","BLOCKED","FAILED"])
def test_terminal_rejection_accepts_bounded_blocker(status):assert state(order_status=status,blockers=("reason",)).blockers==("reason",)
@pytest.mark.parametrize("values",[{},{"warnings":("cancelled",)},{"blockers":("cancelled",)}])
def test_cancelled_requires_reason(values):
 if values: assert state(order_status="CANCELLED",**values).order_status=="CANCELLED"
 else:
  with pytest.raises(ValueError):state(order_status="CANCELLED")
@pytest.mark.parametrize("status",["CREATED","AUTHORIZED","SUBMITTED","REJECTED","BLOCKED","CANCELLED","FAILED"])
def test_only_filled_can_have_fill_price(status):
 kwargs={"order_status":status,"fill_price":100.}
 if status=="AUTHORIZED":kwargs["authorization_id"]="auth"
 if status=="SUBMITTED":kwargs.update(submitted().to_dict());kwargs["fill_price"]=100.;kwargs.pop("schema_version");kwargs.pop("execution_mode");kwargs.pop("live_execution_eligible");kwargs.pop("created_at");kwargs.pop("updated_at")
 if status in {"REJECTED","BLOCKED","FAILED"}:kwargs["blockers"]=("x",)
 with pytest.raises(ValueError):state(**kwargs)
@pytest.mark.parametrize("status",["AUTHORIZED","SUBMITTED","FILLED"])
def test_authorized_states_require_authorization(status):
 kwargs={"order_status":status}
 if status in {"SUBMITTED","FILLED"}:kwargs.update(dict(paper_candidate_id="candidate",canonical_risk_result_id="risk",trading_symbol="OPT",action="BUY",option_type="CALL",position_side="LONG",quantity=100,lots=2,reference_price=100.))
 if status=="FILLED":kwargs.update(execution_result_id="result",fill_price=100.)
 with pytest.raises(ValueError):state(**kwargs)
@pytest.mark.parametrize("field,value",[("paper_candidate_id",None),("canonical_risk_result_id",None),("trading_symbol",None),("action","WAIT"),("option_type","PUT"),("position_side","SHORT"),("quantity",0),("lots",0),("reference_price",0.)])
def test_submitted_requires_actionable_long_identity(field,value):
 with pytest.raises(ValueError):submitted(**{field:value})
@pytest.mark.parametrize("field,value",[("execution_result_id",None),("fill_price",None),("action","SELL"),("option_type","PUT")])
def test_filled_requires_receipt_price_and_mapping(field,value):
 with pytest.raises(ValueError):filled(**{field:value})
@pytest.mark.parametrize("current,next_status",[("CREATED","AUTHORIZED"),("CREATED","BLOCKED"),("CREATED","FAILED"),("AUTHORIZED","SUBMITTED"),("AUTHORIZED","BLOCKED"),("AUTHORIZED","FAILED"),("SUBMITTED","FILLED"),("SUBMITTED","REJECTED"),("SUBMITTED","CANCELLED"),("SUBMITTED","FAILED")])
def test_legal_transitions(current,next_status):
 kwargs={"order_status":current}
 if current in {"AUTHORIZED","SUBMITTED"}:kwargs["authorization_id"]="auth"
 if current=="SUBMITTED":kwargs.update(dict(paper_candidate_id="candidate",canonical_risk_result_id="risk",trading_symbol="OPT",action="BUY",option_type="CALL",position_side="LONG",quantity=100,lots=2,reference_price=100.))
 assert state(**kwargs).can_transition_to(next_status)
@pytest.mark.parametrize("status",["FILLED","REJECTED","BLOCKED","CANCELLED","FAILED"])
def test_terminal_states_cannot_transition(status):
 kwargs={"order_status":status}
 if status=="FILLED":kwargs=filled().to_dict();kwargs.pop("schema_version");kwargs.pop("execution_mode");kwargs.pop("live_execution_eligible");kwargs["created_at"]=NOW;kwargs["updated_at"]=NOW
 elif status in {"REJECTED","BLOCKED","FAILED"}:kwargs["blockers"]=("x",)
 else:kwargs["warnings"]=("x",)
 assert not state(**kwargs).can_transition_to("SUBMITTED")
def test_semantics_exclude_generated_identity_and_times():assert state(paper_order_id="one").semantic_dict()==state(paper_order_id="two",updated_at=NOW+timedelta(minutes=1)).semantic_dict()
@pytest.mark.parametrize("symbol,exchange",[("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")])
def test_canonical_market_identity_is_preserved(symbol,exchange):
 value=state(underlying_symbol=symbol,exchange=exchange);assert value.to_dict()["underlying_symbol"]==symbol and value.semantic_dict()["exchange"]==exchange
@pytest.mark.parametrize("symbol,exchange",[("NIFTY","BSE"),("SENSEX","NSE"),("OTHER","NSE"),("NIFTY 50","NSE")])
def test_market_identity_rejects_noncanonical_or_mismatched_pairs(symbol,exchange):
 with pytest.raises(ValueError):state(underlying_symbol=symbol,exchange=exchange)
