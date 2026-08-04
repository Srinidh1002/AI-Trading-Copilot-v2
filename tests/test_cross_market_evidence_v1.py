from datetime import datetime, timezone
from dataclasses import FrozenInstanceError
from math import inf, nan
import pytest
from services.contracts.cross_market_evidence_v1 import CrossMarketEvidenceV1
NOW=datetime(2026,1,1,tzinfo=timezone.utc)
def make(**x):
 d=dict(cross_market_evidence_id="cross-1",created_at=NOW,primary_symbol="nifty",primary_exchange="nse",related_symbol="sensex",related_exchange="bse",relationship_type="broad_market",timeframe="5m",lookback_observations=30,aligned_sample_size=29,correlation_value=.8,correlation_strength=.8,correlation_state="strong_positive",primary_direction="bullish",related_direction="bullish",confirmation_state="confirming",divergence_state="none",evidence_status="ready",primary_source_id="p",related_source_id="r",primary_source_timestamp=NOW,related_source_timestamp=NOW)
 d.update(x);return CrossMarketEvidenceV1(**d)
def test_valid_and_semantic_are_deterministic():
 value=make();assert value.primary_symbol=="NIFTY";assert value.to_dict()==value.to_dict();assert "cross_market_evidence_id" not in value.semantic_dict()
@pytest.mark.parametrize("primary,exchange,related,related_exchange,relationship",(("SENSEX","BSE","NIFTY","NSE","BROAD_MARKET"),("BANKNIFTY","NSE","FINNIFTY","NSE","FINANCIAL_INDEX"),("FINNIFTY","NSE","BANKNIFTY","NSE","FINANCIAL_INDEX")))
def test_supported_pairs(primary,exchange,related,related_exchange,relationship):assert make(primary_symbol=primary,primary_exchange=exchange,related_symbol=related,related_exchange=related_exchange,relationship_type=relationship)
@pytest.mark.parametrize("value",(nan,inf,-inf,1.1,-1.1))
def test_bad_correlation_rejected(value):
 with pytest.raises(ValueError):make(correlation_value=value)
def test_same_identity_and_sample_mismatch_rejected():
 with pytest.raises(ValueError):make(related_symbol="NIFTY",related_exchange="NSE")
 with pytest.raises(ValueError):make(aligned_sample_size=31)
def test_unavailable_requires_explicit_blocked_shape():
 value=make(correlation_value=None,correlation_strength=0,correlation_state="UNAVAILABLE",confirmation_state="UNAVAILABLE",divergence_state="UNAVAILABLE",evidence_status="UNAVAILABLE",blockers=("missing",))
 assert value.correlation_value is None
def test_frozen_and_naive_rejected():
 with pytest.raises(FrozenInstanceError):make().timeframe="1h"
 with pytest.raises(ValueError):make(created_at=datetime(2026,1,1))
