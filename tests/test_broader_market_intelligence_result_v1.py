from datetime import datetime,timezone
from dataclasses import FrozenInstanceError
import pytest
from services.contracts.broader_market_intelligence_result_v1 import BroaderMarketIntelligenceResultV1
from services.contracts.cross_market_evidence_v1 import CrossMarketEvidenceV1
NOW=datetime(2026,1,1,tzinfo=timezone.utc)
def child(related="SENSEX"):
 return CrossMarketEvidenceV1("x",NOW,"NIFTY","NSE",related,"BSE" if related=="SENSEX" else "NSE","BROAD_MARKET" if related=="SENSEX" else "FINANCIAL_INDEX","5m",30,29,.8,.8,"STRONG_POSITIVE","BULLISH","BULLISH","CONFIRMING","NONE","READY","p","r",NOW,NOW)
def make(**x):
 d=dict(broader_market_intelligence_result_id="result",created_at=NOW,underlying_symbol="NIFTY",exchange="NSE",cross_market_evidence=(child(),),breadth_evidence=None,volatility_context=None,intelligence_status="READY",aggregate_bias="BULLISH",aggregate_strength=.8,confirmation_state="CONFIRMING",divergence_state="NONE",available_component_count=1,unavailable_component_count=0)
 d.update(x);return BroaderMarketIntelligenceResultV1(**d)
def test_ready_and_semantic():assert "broader_market_intelligence_result_id" not in make().semantic_dict()
def test_duplicate_child_and_mismatch_rejected():
 with pytest.raises(ValueError):make(cross_market_evidence=(child(),child()))
 with pytest.raises(ValueError):make(underlying_symbol="SENSEX",exchange="BSE")
def test_conflicting_and_unavailable():
 assert make(intelligence_status="CONFLICTING",aggregate_bias="CONFLICTING",contradictions=("directions conflict",))
 assert make(cross_market_evidence=(),intelligence_status="UNAVAILABLE",aggregate_bias="UNAVAILABLE",aggregate_strength=0,confirmation_state="UNAVAILABLE",divergence_state="UNAVAILABLE",available_component_count=0,unavailable_component_count=0,blockers=("missing",))
def test_frozen():
 with pytest.raises(FrozenInstanceError):make().aggregate_strength=.2
