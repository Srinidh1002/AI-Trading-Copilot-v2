import json
from datetime import date,datetime,timezone,timedelta
import pytest
from services.contracts.trade_plan_v1 import TradePlanV1
NOW=datetime(2026,7,27,10,tzinfo=timezone.utc)
def make(**changes):
    values=dict(trade_plan_id="p",created_at=NOW,snapshot_id="s",analysis_id="a",decision_id="d",selection_id="x",contract_id="c",underlying_symbol="NIFTY",exchange="NSE",action="BUY",option_type="CALL",trading_symbol="SYM",expiry_date=date(2026,7,30),strike=25000,lot_size=50,entry_reference_price=100,entry_price_source="EXPLICIT",stop_loss_price=None,target_price=None,stop_loss_source=None,target_source=None,valid_from=NOW,valid_until=NOW+timedelta(minutes=5),plan_status="READY_FOR_RISK",paper_preparation_eligible=True)
    values.update(changes); return TradePlanV1(**values)
def test_valid_nifty(): assert make().plan_status=="READY_FOR_RISK"
def test_valid_sensex_put(): assert make(underlying_symbol="SENSEX",exchange="BSE",action="SELL",option_type="PUT").lot_size==50
def test_valid_banknifty_call(): assert make(underlying_symbol="BANKNIFTY",exchange="NSE").plan_status=="READY_FOR_RISK"
def test_valid_finnifty_put(): assert make(underlying_symbol="FINNIFTY",exchange="NSE",action="SELL",option_type="PUT").plan_status=="READY_FOR_RISK"
@pytest.mark.parametrize("field,value",[("schema_version","bad"),("trade_plan_id",""),("snapshot_id",""),("decision_id",""),("selection_id",""),("contract_id",""),("trading_symbol",""),("created_at",datetime(2026,7,27)),("valid_from",datetime(2026,7,27)),("valid_until",datetime(2026,7,27)),("valid_until",NOW),("underlying_symbol","BANKNIFTY"),("exchange","MCX"),("action","WAIT"),("option_type","CE"),("option_type","PUT"),("strike",0),("strike",-1),("strike",float("nan")),("strike",float("inf")),("lot_size",0),("lot_size",-1),("lot_size",True),("entry_reference_price",-1),("entry_reference_price",float("nan")),("entry_reference_price",float("inf")),("stop_loss_price",-1),("stop_loss_price",float("nan")),("stop_loss_price",float("inf")),("target_price",-1),("target_price",float("nan")),("target_price",float("inf")),("plan_status","BAD"),("execution_eligible",True),("quantity",1),("lots",1),("capital_required",1),("maximum_loss",1)])
def test_invalid_fields(field,value):
    changes={field:value}
    if field=="underlying_symbol" and value=="BANKNIFTY": changes["exchange"]="BSE"
    with pytest.raises(ValueError): make(**changes)
def test_cross_exchange_and_status_consistency():
    with pytest.raises(ValueError): make(exchange="BSE")
    with pytest.raises(ValueError): make(underlying_symbol="SENSEX")
    with pytest.raises(ValueError): make(blockers=("x",))
    for status in ("BLOCKED","INSUFFICIENT_DATA","EXPIRED","INVALID"):
        with pytest.raises(ValueError): make(plan_status=status,paper_preparation_eligible=False)
def test_defensive_copies_and_serialization():
    metadata={"source":"x"}; blockers=[]; warnings=[]; plan=make(metadata=metadata,blockers=blockers,warnings=warnings); metadata["source"]="y"; blockers.append("x"); warnings.append("x")
    assert plan.metadata=={"source":"x"} and plan.blockers==() and plan.warnings==() and json.loads(plan.to_json())["created_at"].endswith("+00:00")
    assert plan.to_dict()==plan.to_dict() and "trade_plan_id" not in plan.semantic_dict() and "created_at" not in plan.semantic_dict()
def test_unsafe_metadata_rejected():
    class Unsafe:
        def __str__(self): raise AssertionError("unsafe")
    with pytest.raises(ValueError): make(metadata={"x":Unsafe()})
@pytest.mark.parametrize("status",["BLOCKED","INSUFFICIENT_DATA","EXPIRED","INVALID"])
def test_non_ready_permits_honest_no_contract(status):
    plan=make(plan_status=status,paper_preparation_eligible=False,blockers=("blocked",),selection_id=None,contract_id=None,trading_symbol=None,expiry_date=None,strike=None,lot_size=None,option_type=None,action="WAIT")
    assert json.loads(plan.to_json())["contract_id"] is None
def test_non_ready_rejects_partial_identity_and_eligibility():
    with pytest.raises(ValueError): make(plan_status="BLOCKED",paper_preparation_eligible=False,blockers=("x",),contract_id=None)
    with pytest.raises(ValueError): make(plan_status="BLOCKED",paper_preparation_eligible=True,blockers=("x",))
