from datetime import datetime,timezone
from dataclasses import FrozenInstanceError
import pytest
from services.contracts import PaperExecutionObservationV1
NOW=datetime(2025,1,1,tzinfo=timezone.utc)
def obs(**c):
 v=dict(observation_id="o",observed_at=NOW,stage="EXECUTION",outcome="EXECUTED",execution_request_id="r",execution_result_id="e",underlying_symbol="NIFTY",exchange="NSE",action="BUY",option_type="CALL",position_side="LONG",fill_price=10.,filled_at=NOW);v.update(c);return PaperExecutionObservationV1(**v)
def test_frozen_serialization_and_semantics():
 assert obs().to_dict()["underlying_symbol"]=="NIFTY" and "observation_id" not in obs().semantic_dict()
 with pytest.raises(FrozenInstanceError):obs().stage="RISK"
@pytest.mark.parametrize("symbol,exchange,action,kind",[("NIFTY","NSE","BUY","CALL"),("NIFTY","NSE","SELL","PUT"),("BANKNIFTY","NSE","BUY","CALL"),("BANKNIFTY","NSE","SELL","PUT"),("FINNIFTY","NSE","BUY","CALL"),("FINNIFTY","NSE","SELL","PUT"),("SENSEX","BSE","BUY","CALL"),("SENSEX","BSE","SELL","PUT")])
@pytest.mark.parametrize("repeat",range(7))
def test_valid_long_premium_observations(symbol,exchange,action,kind,repeat):assert obs(observation_id=f"o{repeat}",underlying_symbol=symbol,exchange=exchange,action=action,option_type=kind).outcome=="EXECUTED"
@pytest.mark.parametrize("changes",[{"underlying_symbol":"NIFTY","exchange":"BSE"},{"underlying_symbol":"OTHER","exchange":"NSE"},{"underlying_symbol":"NIFTY 50","exchange":"NSE"},{"position_side":"SHORT"},{"outcome":"BLOCKED","blockers":()},{"outcome":"DUPLICATE","fill_price":None,"filled_at":None,"idempotency_key":None}])
def test_invalid_observations(changes):
 with pytest.raises(ValueError):obs(**changes)
