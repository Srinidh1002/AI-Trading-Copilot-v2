from datetime import datetime,timezone
from dataclasses import FrozenInstanceError
import pytest
from services.contracts.market_breadth_evidence_v1 import MarketBreadthEvidenceV1
NOW=datetime(2026,1,1,tzinfo=timezone.utc)
def make(**x):
 d=dict(market_breadth_evidence_id="breadth-1",created_at=NOW,underlying_symbol="NIFTY",exchange="NSE",source_id="source",source_timestamp=NOW,advance_count=60,decline_count=30,unchanged_count=10,total_count=100,covered_count=100,coverage_ratio=1,advance_decline_ratio=2,breadth_bias="BULLISH",breadth_strength=.7,participation_state="BROAD",heavyweight_contribution_state="CONFIRMS",evidence_status="READY")
 d.update(x);return MarketBreadthEvidenceV1(**d)
def test_valid_bullish_and_serialization():assert make().to_dict()["advance_count"]==60
@pytest.mark.parametrize("bias,advance,decline,ratio",( ("BEARISH",0,60,0),("NEUTRAL",40,40,1)))
def test_zero_is_data_not_unavailable(bias,advance,decline,ratio):assert make(breadth_bias=bias,advance_count=advance,decline_count=decline,unchanged_count=100-advance-decline,advance_decline_ratio=ratio)
def test_inconsistent_counts_rejected():
 with pytest.raises(ValueError):make(total_count=99)
 with pytest.raises(ValueError):make(covered_count=101)
def test_unavailable_is_not_neutral():
 value=make(advance_count=None,decline_count=None,unchanged_count=None,total_count=None,covered_count=0,coverage_ratio=0,advance_decline_ratio=None,breadth_bias="UNAVAILABLE",breadth_strength=0,participation_state="UNAVAILABLE",heavyweight_contribution_state="UNAVAILABLE",evidence_status="UNAVAILABLE",blockers=("missing",))
 assert value.advance_count is None
def test_frozen(): 
 with pytest.raises(FrozenInstanceError):make().breadth_strength=.2
