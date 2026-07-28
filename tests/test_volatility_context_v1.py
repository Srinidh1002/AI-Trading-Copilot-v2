from datetime import datetime,timezone
from dataclasses import FrozenInstanceError
import pytest
from services.contracts.volatility_context_v1 import VolatilityContextV1
NOW=datetime(2026,1,1,tzinfo=timezone.utc)
def make(**x):
 d=dict(volatility_context_id="vix-1",created_at=NOW,underlying_symbol="NIFTY",exchange="NSE",volatility_symbol="INDIA_VIX",volatility_exchange="NSE",source_id="vix",source_timestamp=NOW,volatility_value=16,volatility_change_percent=1,volatility_regime="NORMAL",volatility_direction="RISING",volatility_strength=.3,context_status="READY")
 d.update(x);return VolatilityContextV1(**d)
@pytest.mark.parametrize("regime",("LOW","NORMAL","HIGH","EXTREME"))
def test_normalized_regimes(regime):assert make(volatility_regime=regime)
def test_unavailable_and_negative_rejection():
 assert make(volatility_value=None,volatility_change_percent=None,volatility_regime="UNAVAILABLE",volatility_direction="UNAVAILABLE",volatility_strength=0,context_status="UNAVAILABLE",blockers=("missing",))
 with pytest.raises(ValueError):make(volatility_value=-1)
def test_identity_and_frozen():
 with pytest.raises(ValueError):make(volatility_symbol="VIX")
 with pytest.raises(FrozenInstanceError):make().volatility_value=2
