from datetime import datetime, timezone
import pytest
from services.contracts.certified_live_captured_evidence_v1 import CertifiedLiveCapturedEvidenceV1
NOW=datetime(2026,8,3,tzinfo=timezone.utc)
def build(**changes):
 v=dict(underlying_symbol="NIFTY",spot_exchange="NSE",spot_token="99926000",option_exchange="NFO",spot_payload={"ltp":1},candle_rows_by_timeframe={"5m":()},option_contracts=(),provider_timestamp=NOW,evaluated_at=NOW);v.update(changes);return CertifiedLiveCapturedEvidenceV1(**v)
def test_identity_and_safe_summary():assert build().to_dict()["spot_token"]=="99926000"
def test_rejects_wrong_identity_and_secret():
 with pytest.raises(ValueError):build(spot_exchange="BSE")
 with pytest.raises(ValueError):build(spot_payload={"api_secret":"x"})

def test_capture_mappings_cannot_be_mutated():
 evidence=build(spot_payload={"ltp":1,"nested":{"value":2}})
 with pytest.raises(TypeError): evidence.spot_payload["ltp"]=2
 with pytest.raises(TypeError): evidence.spot_payload["nested"]["value"]=3
