from datetime import datetime,timezone
from dataclasses import FrozenInstanceError
import pytest
from services.contracts.market_breadth_snapshot_v1 import MarketBreadthSnapshotV1
NOW=datetime(2026,1,1,tzinfo=timezone.utc)
def make(**x):
 d=dict(market_breadth_snapshot_id="b",created_at=NOW,underlying_symbol="NIFTY",exchange="NSE",source_id="s",source_timestamp=NOW,advance_count=60,decline_count=30,unchanged_count=10,total_count=100,covered_count=100)
 d.update(x);return MarketBreadthSnapshotV1(**d)
def test_snapshot_is_frozen_and_serializes(): 
 with pytest.raises(FrozenInstanceError):make().covered_count=1
 assert "market_breadth_snapshot_id" not in make().semantic_dict()
def test_negative_and_naive_rejected():
 with pytest.raises(ValueError):make(advance_count=-1)
 with pytest.raises(ValueError):make(created_at=datetime(2026,1,1))
