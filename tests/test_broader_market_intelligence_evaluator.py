from datetime import datetime,timezone
import pytest
from services.broader_market_intelligence import evaluate_broader_market_intelligence
from services.contracts.cross_market_evidence_v1 import CrossMarketEvidenceV1
NOW=datetime(2026,1,1,tzinfo=timezone.utc)
def cross(**x):
 d=dict(cross_market_evidence_id="x",created_at=NOW,primary_symbol="NIFTY",primary_exchange="NSE",related_symbol="SENSEX",related_exchange="BSE",relationship_type="BROAD_MARKET",timeframe="5m",lookback_observations=30,aligned_sample_size=30,correlation_value=.8,correlation_strength=.8,correlation_state="STRONG_POSITIVE",primary_direction="BULLISH",related_direction="BULLISH",confirmation_state="CONFIRMING",divergence_state="NONE",evidence_status="READY",primary_source_id="p",related_source_id="r",primary_source_timestamp=NOW,related_source_timestamp=NOW)
 d.update(x);return CrossMarketEvidenceV1(**d)
def test_cross_market_only_is_warning_ready_for_missing_optional_components():
 result=evaluate_broader_market_intelligence(underlying_symbol="NIFTY",exchange="NSE",cross_market_evidence=(cross(),),breadth_evidence=None,volatility_context=None,created_at=NOW,result_id="r")
 assert result.intelligence_status=="READY_WITH_WARNINGS";assert result.aggregate_bias=="BULLISH"
def test_missing_mandatory_and_bad_child_types():
 result=evaluate_broader_market_intelligence(underlying_symbol="NIFTY",exchange="NSE",cross_market_evidence=(),breadth_evidence=None,volatility_context=None,created_at=NOW,result_id="r")
 assert result.intelligence_status=="BLOCKED"
 with pytest.raises(TypeError):evaluate_broader_market_intelligence(underlying_symbol="NIFTY",exchange="NSE",cross_market_evidence=[],breadth_evidence=None,volatility_context=None,created_at=NOW,result_id="r")
