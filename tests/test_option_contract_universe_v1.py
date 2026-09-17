import json
from datetime import date,datetime,timezone
import pytest
from services.contracts.option_contract_v1 import OptionContractV1
from services.contracts.option_contract_universe_v1 import OptionContractUniverseV1
NOW=datetime(2026,7,27,tzinfo=timezone.utc)
def contract(identity="NIFTY",exchange="NSE",cid="c",strike=25000): return OptionContractV1(cid,identity,exchange,cid,"CALL",strike,date(2026,7,30),50,NOW)
def make(**changes):
    values=dict(universe_id="u",underlying_symbol="NIFTY",exchange="NSE",captured_at=NOW,spot_price=25000,contracts=(contract(),),source_name="synthetic",trusted=True); values.update(changes); return OptionContractUniverseV1(**values)
def test_valid_nifty(): assert make().underlying_symbol=="NIFTY"
def test_valid_sensex(): assert make(underlying_symbol="SENSEX",exchange="BSE",contracts=(contract("SENSEX","BSE"),)).exchange=="BSE"
def test_empty_allowed(): assert make(contracts=()).contracts==()
@pytest.mark.parametrize("field,value",[("schema_version","bad"),("universe_id",""),("underlying_symbol",""),("exchange",""),("underlying_symbol","BANKNIFTY"),("exchange","MCX"),("spot_price",0),("spot_price",-1),("spot_price",float("nan")),("spot_price",float("inf")),("captured_at",datetime(2026,7,27))])
def test_invalid_universe_values(field,value):
    with pytest.raises(ValueError): make(**{field:value})
def test_cross_exchange_identities_rejected():
    with pytest.raises(ValueError): make(exchange="BSE")
    with pytest.raises(ValueError): make(underlying_symbol="SENSEX")
def test_contract_identity_and_duplicates_rejected():
    with pytest.raises(ValueError): make(contracts=(contract("SENSEX","BSE"),))
    with pytest.raises(ValueError): make(contracts=(contract(),contract()))
def test_ordering_and_collection_copy():
    items=[contract(cid="z",strike=25100),contract(cid="a",strike=25000)]; universe=make(contracts=items); items.clear(); assert [c.contract_id for c in universe.contracts]==["a","z"]
def test_metadata_warnings_and_json_are_deterministic():
    metadata={"source":"synthetic"}; warnings=["warning"]; universe=make(metadata=metadata,warnings=warnings); metadata["source"]="changed"; warnings.append("changed")
    assert universe.metadata=={"source":"synthetic"} and universe.warnings==("warning",) and universe.to_dict()==universe.semantic_dict() and json.loads(universe.to_json())["captured_at"].endswith("+00:00")
def test_invalid_contract_and_unsafe_metadata_rejected():
    with pytest.raises(ValueError): make(contracts=(object(),))
    class Unsafe:
        def __str__(self): raise AssertionError("unsafe")
    with pytest.raises(ValueError): make(metadata={"x":Unsafe()})
