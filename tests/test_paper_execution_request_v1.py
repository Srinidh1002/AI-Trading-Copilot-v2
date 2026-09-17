from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta, timezone
import pytest
from services.contracts import PaperExecutionRequestV1

NOW=datetime(2026,7,27,10,tzinfo=timezone.utc)
def request(**c):
    v=dict(execution_request_id="request",created_at=NOW,authorization_id="authorization",idempotency_key="key",snapshot_id="snapshot",analysis_id="analysis",decision_id="decision",trade_plan_result_id="plan-result",trade_plan_id="plan",sizing_result_id="sizing",canonical_risk_result_id="risk",paper_candidate_id="candidate",underlying_symbol="NIFTY",exchange="NSE",action="BUY",option_type="CALL",position_side="LONG",trading_symbol="NIFTYOPT",expiry_date=date(2026,7,30),strike=25000.0,lot_size=50,quantity=100,lots=2,entry_reference_price=100.0,stop_loss_price=90.0,target_price=120.0,capital_required=10000.0,maximum_loss=1000.0,reward_risk_ratio=2.0,valid_from=NOW,valid_until=NOW+timedelta(minutes=5)); v.update(c); return PaperExecutionRequestV1(**v)

@pytest.mark.parametrize("symbol,exchange,action,kind",[("NIFTY","NSE","BUY","CALL"),("NIFTY","NSE","SELL","PUT"),("BANKNIFTY","NSE","BUY","CALL"),("BANKNIFTY","NSE","SELL","PUT"),("FINNIFTY","NSE","BUY","CALL"),("FINNIFTY","NSE","SELL","PUT"),("SENSEX","BSE","BUY","CALL"),("SENSEX","BSE","SELL","PUT")])
def test_supported_long_premium_requests(symbol,exchange,action,kind): assert request(underlying_symbol=symbol,exchange=exchange,action=action,option_type=kind).live_execution_eligible is False
def test_frozen_slots_and_determinism():
    value=request(); assert not hasattr(value,"__dict__") and value==request() and value.to_dict()==request().to_dict()
    with pytest.raises(FrozenInstanceError): value.quantity=1
def test_serialization_is_primitive_and_stable():
    value=request(); assert value.to_json()==request().to_json() and value.to_dict()["created_at"]==NOW.isoformat() and value.to_dict()["expiry_date"]=="2026-07-30"
@pytest.mark.parametrize("field,value",[("execution_request_id",""),("authorization_id",""),("idempotency_key",""),("snapshot_id",""),("analysis_id",""),("decision_id",""),("trade_plan_result_id",""),("trade_plan_id",""),("sizing_result_id",""),("canonical_risk_result_id",""),("paper_candidate_id",""),("trading_symbol","")])
def test_empty_linkage_is_rejected(field,value):
    with pytest.raises(ValueError): request(**{field:value})
@pytest.mark.parametrize("field,value",[("created_at",datetime(2026,7,27)),("valid_from",datetime(2026,7,27)),("valid_until",datetime(2026,7,27)),("execution_mode","LIVE"),("live_execution_eligible",True),("schema_version","bad"),("exchange","BSE"),("action","WAIT"),("option_type","PUT"),("position_side","SHORT"),("expiry_date",None),("strike",0),("lot_size",0),("quantity",0),("lots",0),("entry_reference_price",0),("stop_loss_price",0),("target_price",0),("capital_required",0),("maximum_loss",0),("reward_risk_ratio",0)])
def test_invalid_controls_and_values_are_rejected(field,value):
    with pytest.raises(ValueError): request(**{field:value})
def test_banknifty_bse_identity_mismatch_is_rejected():
    with pytest.raises(ValueError): request(underlying_symbol="BANKNIFTY",exchange="BSE")
@pytest.mark.parametrize("changes",[{"quantity":50,"lots":2},{"stop_loss_price":100},{"target_price":100},{"valid_until":NOW},{"action":"BUY","option_type":"PUT"},{"action":"SELL","option_type":"CALL"}])
def test_invalid_geometry_mapping_and_arithmetic_are_rejected(changes):
    with pytest.raises(ValueError): request(**changes)
def test_semantic_serialization_excludes_generated_identity_and_time():
    assert request(execution_request_id="one",created_at=NOW).semantic_dict()==request(execution_request_id="two",created_at=NOW+timedelta(minutes=1)).semantic_dict()
