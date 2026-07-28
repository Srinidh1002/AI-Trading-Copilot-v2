from dataclasses import FrozenInstanceError
from datetime import datetime,timedelta,timezone
import pytest
from services.contracts import PaperExecutionResultV1
NOW=datetime(2026,7,27,10,tzinfo=timezone.utc)
def result(**c):
 v=dict(execution_result_id="result",execution_request_id="request",created_at=NOW,idempotency_key="key",execution_status="ACCEPTED",authorization_id="auth",paper_candidate_id="candidate",canonical_risk_result_id="risk",trade_plan_id="plan",sizing_result_id="size",submitted_at=NOW);v.update(c);return PaperExecutionResultV1(**v)
def filled(**c):
 v=dict(execution_status="FILLED",underlying_symbol="NIFTY",exchange="NSE",action="BUY",option_type="CALL",position_side="LONG",trading_symbol="OPT",requested_quantity=100,filled_quantity=100,requested_lots=2,filled_lots=2,reference_price=100.,fill_price=100.,capital_used=10000.,realized_maximum_loss=1000.,filled_at=NOW+timedelta(seconds=1));v.update(c);return result(**v)
@pytest.mark.parametrize("action,kind",[("BUY","CALL"),("SELL","PUT")])
def test_filled_long_directions(action,kind): assert filled(action=action,option_type=kind).execution_status=="FILLED"
def test_frozen_slots_and_serialization():
 value=filled();assert not hasattr(value,"__dict__") and value.to_json()==filled().to_json()
 with pytest.raises(FrozenInstanceError):value.execution_status="FAILED"
@pytest.mark.parametrize("field",["execution_result_id","execution_request_id","idempotency_key"])
def test_required_ids(field):
 with pytest.raises(ValueError):result(**{field:""})
@pytest.mark.parametrize("field,value",[("created_at",datetime(2026,7,27)),("execution_mode","LIVE"),("live_execution_eligible",True),("schema_version","bad"),("execution_status","BAD"),("submitted_at",datetime(2026,7,27)),("filled_at",datetime(2026,7,27)),("blockers",("",)),("warnings",("",))])
def test_control_values(field,value):
 with pytest.raises(ValueError):result(**{field:value})
@pytest.mark.parametrize("status",["REJECTED","BLOCKED","FAILED"])
def test_nonapproval_statuses_require_blockers(status):
 with pytest.raises(ValueError):result(execution_status=status,submitted_at=None)
@pytest.mark.parametrize("status",["REJECTED","BLOCKED","FAILED"])
def test_nonapproval_statuses_allow_bounded_blockers(status): assert result(execution_status=status,submitted_at=None,blockers=("blocked",)).blockers==("blocked",)
@pytest.mark.parametrize("field,value",[("filled_quantity",1),("filled_lots",1),("fill_price",1.),("capital_used",1.),("realized_maximum_loss",1.),("filled_at",NOW)])
def test_nonfilled_statuses_cannot_fabricate_fills(field,value):
 with pytest.raises(ValueError):result(**{field:value})
@pytest.mark.parametrize("field,value",[("authorization_id",None),("paper_candidate_id",None),("canonical_risk_result_id",None),("trade_plan_id",None),("sizing_result_id",None),("submitted_at",None)])
def test_accepted_requires_complete_linkage(field,value):
 with pytest.raises(ValueError):result(**{field:value})
@pytest.mark.parametrize("field,value",[("underlying_symbol","OTHER"),("exchange","BSE"),("action","WAIT"),("option_type","PUT"),("position_side","SHORT"),("trading_symbol",None),("requested_quantity",0),("filled_quantity",0),("requested_lots",0),("filled_lots",0),("reference_price",0.),("fill_price",0.),("capital_used",0.),("realized_maximum_loss",0.),("submitted_at",None),("filled_at",None)])
def test_filled_requires_complete_long_identity_and_values(field,value):
 with pytest.raises(ValueError):filled(**{field:value})
@pytest.mark.parametrize("changes",[{"filled_quantity":101},{"filled_lots":3},{"filled_at":NOW-timedelta(seconds=1)},{"blockers":("no",)}])
def test_filled_ordering_and_counts(changes):
 with pytest.raises(ValueError):filled(**changes)
@pytest.mark.parametrize("message",[(),("duplicate",)])
def test_duplicate_explanation(message):
 if message: assert result(execution_status="DUPLICATE",submitted_at=None,warnings=message).execution_status=="DUPLICATE"
 else:
  with pytest.raises(ValueError):result(execution_status="DUPLICATE",submitted_at=None)
def test_result_semantics_exclude_generated_id_and_time():assert result(execution_result_id="a",created_at=NOW).semantic_dict()==result(execution_result_id="b",created_at=NOW+timedelta(minutes=1)).semantic_dict()
