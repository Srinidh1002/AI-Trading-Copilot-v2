import json
from datetime import date,datetime,timezone
import pytest
from services.contracts.selected_option_contract_v1 import SelectedOptionContractV1
NOW=datetime(2026,7,27,tzinfo=timezone.utc)
def make(**changes):
    values=dict(selection_id="s",selected_at=NOW,snapshot_id="snap",decision_id="dec",universe_id="uni",contract_id="con",underlying_symbol="NIFTY",exchange="NSE",action="BUY",option_type="CALL",trading_symbol="NIFTY-C",instrument_token=None,expiry_date=date(2026,7,30),strike=25000,lot_size=50,reference_spot_price=25000,reference_option_price=100,reference_price_source="MID",expiry_selection_policy="EARLIEST_ELIGIBLE",strike_selection_policy="NEAREST_ATM",selection_valid=True); values.update(changes); return SelectedOptionContractV1(**values)
def test_valid_call(): assert make().selection_valid
def test_valid_put(): assert make(underlying_symbol="SENSEX",exchange="BSE",action="SELL",option_type="PUT").option_type=="PUT"
def test_valid_banknifty_call(): assert make(underlying_symbol="BANKNIFTY",exchange="NSE").selection_valid
def test_valid_finnifty_put(): assert make(underlying_symbol="FINNIFTY",exchange="NSE",action="SELL",option_type="PUT").selection_valid
@pytest.mark.parametrize("field,value",[("schema_version","bad"),("selection_id",""),("snapshot_id",""),("decision_id",""),("universe_id",""),("contract_id",""),("trading_symbol",""),("selected_at",datetime(2026,7,27)),("underlying_symbol","BANKNIFTY"),("exchange","MCX"),("action","WAIT"),("option_type","CE"),("option_type","PUT"),("strike",0),("strike",-1),("strike",float("nan")),("strike",float("inf")),("lot_size",0),("lot_size",-1),("lot_size",True),("reference_spot_price",0),("reference_spot_price",-1),("reference_spot_price",float("nan")),("reference_spot_price",float("inf")),("reference_option_price",-1),("reference_price_source","X"),("expiry_selection_policy","X"),("strike_selection_policy","X")])
def test_invalid_values(field,value):
    changes={field:value}
    if field=="underlying_symbol" and value=="BANKNIFTY": changes["exchange"]="BSE"
    with pytest.raises(ValueError): make(**changes)
def test_cross_exchange_rejected():
    with pytest.raises(ValueError): make(exchange="BSE")
    with pytest.raises(ValueError): make(underlying_symbol="SENSEX")
def test_invalid_validity_consistency_rejected():
    with pytest.raises(ValueError): make(blockers=("x",))
    with pytest.raises(ValueError): make(selection_valid=False)
def test_copies_and_serialization():
    metadata={"a":1}; blockers=[]; warnings=[]; selection=make(metadata=metadata,blockers=blockers,warnings=warnings); metadata["a"]=2; blockers.append("x"); warnings.append("x")
    assert selection.metadata=={"a":1} and selection.blockers==() and selection.warnings==() and json.loads(selection.to_json())["selected_at"].endswith("+00:00")
    assert selection.to_dict()==selection.to_dict() and "selection_id" not in selection.semantic_dict() and "selected_at" not in selection.semantic_dict()
def test_unsafe_metadata_rejected():
    class Unsafe:
        def __str__(self): raise AssertionError("unsafe")
    with pytest.raises(ValueError): make(metadata={"x":Unsafe()})
@pytest.mark.parametrize("field",["universe_id","contract_id","trading_symbol","expiry_date","strike","lot_size"])
def test_valid_selection_requires_complete_identity(field):
    with pytest.raises(ValueError): make(**{field:None})
def test_blocked_selection_allows_no_contract_identity_or_direction():
    value=make(selection_valid=False,blockers=("No contract",),universe_id=None,contract_id=None,trading_symbol=None,expiry_date=None,strike=None,lot_size=None,option_type=None,action="WAIT")
    assert value.contract_id is None and json.loads(value.to_json())["contract_id"] is None
def test_blocked_selection_rejects_partial_contract_identity():
    with pytest.raises(ValueError): make(selection_valid=False,blockers=("No contract",),contract_id=None)
