from datetime import datetime,timezone
from dataclasses import FrozenInstanceError
import pytest
from services.contracts.volatility_snapshot_v1 import VolatilitySnapshotV1
NOW=datetime(2026,1,1,tzinfo=timezone.utc)
def make(**x):
 d=dict(volatility_snapshot_id="v",created_at=NOW,underlying_symbol="NIFTY",exchange="NSE",volatility_symbol="INDIA_VIX",volatility_exchange="NSE",source_id="s",source_timestamp=NOW,volatility_value=15,previous_volatility_value=10,volatility_change_percent=50,normalized_volatility_regime="NORMAL")
 d.update(x);return VolatilitySnapshotV1(**d)
def test_snapshot_frozen_and_derives_change():
 assert make(volatility_change_percent=None).volatility_change_percent==50
 with pytest.raises(FrozenInstanceError):make().volatility_value=2
def test_unavailable_and_consistency():
 assert make(volatility_value=None,normalized_volatility_regime="UNAVAILABLE").volatility_value is None
 with pytest.raises(ValueError):make(volatility_change_percent=1)
 with pytest.raises(ValueError):make(volatility_symbol="VIX")
