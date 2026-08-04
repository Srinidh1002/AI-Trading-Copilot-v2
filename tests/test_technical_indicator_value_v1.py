from dataclasses import FrozenInstanceError
import pytest
from services.contracts import TechnicalIndicatorValueV1

def valid(**changes):
    data=dict(indicator_name="RSI",timeframe="5m",value=50.0,signal="NEUTRAL",status="VALID",minimum_required_candles=15,available_complete_candles=20,parameters=(("period",14),))
    data.update(changes); return TechnicalIndicatorValueV1(**data)

@pytest.mark.parametrize("name", ["RSI","EMA","MACD","ATR","ADX","BOLLINGER","VWAP","VOLUME","SMA"])
@pytest.mark.parametrize("timeframe", ["5m","15m","1h","1d"])
def test_valid_indicator_values(name,timeframe): assert valid(indicator_name=name,timeframe=timeframe).to_dict()["status"] == "VALID"

@pytest.mark.parametrize("status", ["INSUFFICIENT_HISTORY","UNAVAILABLE","MALFORMED","FAILED"])
@pytest.mark.parametrize("signal", ["NONE","NEUTRAL","BULLISH"])
def test_unavailable_states_need_blocked_null_value(status,signal): assert valid(status=status,signal=signal,value=None,blockers=("unavailable",)).value is None

@pytest.mark.parametrize("change", [{"indicator_name":""},{"timeframe":"1m"},{"status":"READY"},{"signal":"BUY"},{"minimum_required_candles":0},{"available_complete_candles":-1},{"value":float("nan")},{"value":True},{"parameters":(("x",1),("x",2))},{"parameters":(("x",float("inf")),)}])
def test_invalid_fields_rejected(change):
    with pytest.raises(ValueError): valid(**change)

def test_unavailable_value_is_rejected():
    with pytest.raises(ValueError): valid(status="FAILED",value=1.0,blockers=("failed",))
def test_unavailable_without_blocker_is_rejected():
    with pytest.raises(ValueError): valid(status="FAILED",value=None)
def test_valid_without_value_is_rejected():
    with pytest.raises(ValueError): valid(value=None)
def test_serialization_is_primitive_and_deterministic(): assert valid().to_dict() == valid().to_dict()
def test_contract_is_frozen():
    with pytest.raises(FrozenInstanceError): valid().value=3.0
