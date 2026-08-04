from datetime import datetime,timezone
from types import MappingProxyType
import pytest
from services.contracts.market_regime_input_v1 import MarketRegimeInputV1
T=datetime(2026,1,1,tzinfo=timezone.utc)
SLOTS=("technical_intelligence","broader_market_intelligence","external_market_context","market_session_validation","technical_regime_component","broader_market_regime_component","external_context_regime_component")
def make(**x):
 d=dict(market_regime_input_id="INPUT",created_at=T,underlying_symbol="NIFTY",exchange="NSE");d.update(x);return MarketRegimeInputV1(**d)
def test_all_none_partial_and_provenance_are_supported_deterministically():
 source={"Z":T,"A":T};value=make(source_timestamps=source,metadata={"fixture":"typed"})
 assert tuple(value.source_timestamps)==("A","Z") and value.to_dict()==value.to_dict() and value.to_json()==value.to_json() and value.semantic_dict()==value.semantic_dict()
 with pytest.raises(TypeError):value.source_timestamps["X"]=T
 with pytest.raises(TypeError):value.metadata["X"]="Y"
def test_every_child_slot_rejects_untyped_values():
 for slot in SLOTS:
  for value in (object(),{},MappingProxyType({})):
   with pytest.raises(TypeError):make(**{slot:value})
  assert make(**{slot:None})
def test_identity_timestamp_metadata_and_execution_validation():
 for changes in ({"market_regime_input_id":" "},{"created_at":T.replace(tzinfo=None)},{"underlying_symbol":"NIFTY","exchange":"BSE"},{"source_timestamps":{"":T}},{"source_timestamps":{"S":T.replace(tzinfo=None)}},{"metadata":{"bad":object()}},{"execution_mode":"LIVE"},{"live_execution_eligible":True}):
  with pytest.raises((ValueError,TypeError)):make(**changes)
@pytest.mark.parametrize("symbol,exchange",(("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")))
def test_all_canonical_identities_accept_all_none_bundle(symbol,exchange):assert MarketRegimeInputV1("I",T,symbol,exchange)
