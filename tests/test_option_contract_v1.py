import json
from datetime import date, datetime, timezone
import pytest
from services.contracts.option_contract_v1 import OptionContractV1

NOW=datetime(2026,7,27,10,tzinfo=timezone.utc)
def make(**changes):
    values=dict(contract_id="contract-1",underlying_symbol="NIFTY",exchange="NSE",trading_symbol="NIFTY26C",option_type="CALL",strike=25000,expiry_date=date(2026,7,30),lot_size=50,market_timestamp=NOW)
    values.update(changes); return OptionContractV1(**values)

def test_valid_nifty_call(): assert make().option_type == "CALL"
def test_valid_sensex_put(): assert make(underlying_symbol="SENSEX",exchange="BSE",option_type="PUT").lot_size == 50
def test_valid_banknifty_call(): assert make(underlying_symbol="BANKNIFTY",exchange="NSE").lot_size == 50
def test_valid_finnifty_put(): assert make(underlying_symbol="FINNIFTY",exchange="NSE",option_type="PUT").lot_size == 50
@pytest.mark.parametrize("field,value",[("schema_version","bad"),("contract_id",""),("trading_symbol",""),("underlying_symbol","BANKNIFTY"),("exchange","MCX"),("underlying_symbol","NIFTY"),("underlying_symbol","SENSEX"),("option_type","CE"),("strike",0),("strike",-1),("strike",float("nan")),("strike",float("inf")),("lot_size",0),("lot_size",-1),("lot_size",True),("market_timestamp",datetime(2026,7,27)),("last_price",-1),("bid_price",-1),("ask_price",-1),("open_interest",-1),("volume",-1),("implied_volatility",-1),("tick_size",-1),("last_price",float("nan")),("last_price",float("inf"))])
def test_invalid_contract_values(field,value):
    changes={field:value}
    if field=="underlying_symbol" and value=="NIFTY": changes["exchange"]="BSE"
    if field=="underlying_symbol" and value=="SENSEX": changes["exchange"]="NSE"
    if field=="underlying_symbol" and value=="BANKNIFTY": changes["exchange"]="BSE"
    with pytest.raises(ValueError): make(**changes)

def test_metadata_is_copied_without_mutating_input():
    metadata={"source":"synthetic"}; contract=make(metadata=metadata); metadata["source"]="changed"
    assert contract.metadata == {"source":"synthetic"} and metadata == {"source":"changed"}
def test_metadata_unknown_object_rejected_without_string_conversion():
    class Unsafe:
        def __str__(self): raise AssertionError("unsafe")
    with pytest.raises(ValueError): make(metadata={"unsafe":Unsafe()})
def test_serialization_is_deterministic_and_datetime_is_aware():
    contract=make(); assert contract.to_dict()==contract.to_dict(); assert contract.to_json()==contract.to_json(); assert json.loads(contract.to_json())["market_timestamp"].endswith("+00:00")
def test_semantic_dict_is_stable_and_preserves_caller_contract_identity():
    contract=make(); assert contract.semantic_dict()==contract.semantic_dict(); assert contract.semantic_dict()["contract_id"]=="contract-1"
