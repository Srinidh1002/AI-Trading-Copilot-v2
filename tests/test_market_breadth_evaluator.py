from datetime import datetime,timedelta,timezone
import pytest
from services.broader_market_intelligence import evaluate_market_breadth
from services.contracts.market_breadth_snapshot_v1 import MarketBreadthSnapshotV1
NOW=datetime(2026,1,1,tzinfo=timezone.utc)
def snap(**x):
 d=dict(market_breadth_snapshot_id="b",created_at=NOW,underlying_symbol="NIFTY",exchange="NSE",source_id="s",source_timestamp=NOW,advance_count=60,decline_count=30,unchanged_count=10,total_count=100,covered_count=100,heavyweight_contribution_state="CONFIRMS")
 d.update(x);return MarketBreadthSnapshotV1(**d)
def test_bullish_bearish_neutral_and_serialization():
 assert evaluate_market_breadth(breadth_snapshot=snap(),created_at=NOW,evidence_id="e").breadth_bias=="BULLISH"
 assert evaluate_market_breadth(breadth_snapshot=snap(advance_count=20,decline_count=60,unchanged_count=20),created_at=NOW,evidence_id="e").breadth_bias=="BEARISH"
 assert evaluate_market_breadth(breadth_snapshot=snap(advance_count=40,decline_count=40,unchanged_count=20),created_at=NOW,evidence_id="e").to_json()
def test_zero_and_unavailable_counts():
 assert evaluate_market_breadth(breadth_snapshot=snap(advance_count=0,decline_count=60,unchanged_count=40),created_at=NOW,evidence_id="e").advance_decline_ratio==0
 assert evaluate_market_breadth(breadth_snapshot=snap(advance_count=None,decline_count=None,unchanged_count=None,total_count=None,covered_count=0),created_at=NOW,evidence_id="e").evidence_status=="UNAVAILABLE"
def test_inconsistent_partial_and_stale():
 assert evaluate_market_breadth(breadth_snapshot=snap(total_count=99),created_at=NOW,evidence_id="e").evidence_status=="BLOCKED"
 assert evaluate_market_breadth(breadth_snapshot=snap(is_partial=True),created_at=NOW,evidence_id="e").evidence_status=="BLOCKED"
 assert evaluate_market_breadth(breadth_snapshot=snap(source_timestamp=NOW-timedelta(hours=1)),created_at=NOW,evidence_id="e").evidence_status=="UNAVAILABLE"
def test_type_safety():
 with pytest.raises(TypeError):evaluate_market_breadth(breadth_snapshot={},created_at=NOW,evidence_id="e")
