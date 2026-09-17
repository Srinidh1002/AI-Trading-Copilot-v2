from datetime import datetime, timezone
import pytest
from services.contracts.external_market_observation_v1 import ExternalMarketObservationV1
from services.contracts.global_market_context_result_v1 import GlobalMarketContextResultV1
NOW=datetime(2026,1,1,tzinfo=timezone.utc)
def obs(name="SP500",direction="POSITIVE"):
 return ExternalMarketObservationV1(name,NOW,name,"INDEX_CLOSE" if name!="GIFT_NIFTY" else "PREMARKET_INDICATOR","UNITED_STATES" if name!="GIFT_NIFTY" else "INDIA","EQUITY_INDEX" if name!="GIFT_NIFTY" else "EQUITY_INDEX_FUTURE","S",NOW,"PREVIOUS_SESSION_CLOSE",101,100,1,1,direction,"READY")
def make(**x):
 o=x.pop("observations",(obs(),));d=dict(global_market_context_result_id="r",created_at=NOW,underlying_symbol="NIFTY",exchange="NSE",observations=o,context_status="READY",aggregate_direction="POSITIVE",aggregate_strength=.5,confirmation_state="CONFIRMING",available_observation_count=len(o),unavailable_observation_count=0,delayed_observation_count=0,positive_weight=.5,negative_weight=0,flat_weight=0,source_timestamps={a.canonical_name:a.source_timestamp for a in o});d.update(x);return GlobalMarketContextResultV1(**d)
def test_result_contract_ready_and_serialization():assert make().semantic_dict()["aggregate_direction"]=="POSITIVE"
def test_result_contract_status_invariants():
 with pytest.raises(ValueError):make(context_status="BLOCKED")
 with pytest.raises(ValueError):make(context_status="UNAVAILABLE",aggregate_direction="POSITIVE",aggregate_strength=.1,confirmation_state="UNAVAILABLE")
 with pytest.raises(ValueError):make(observations=(obs(),obs()))
