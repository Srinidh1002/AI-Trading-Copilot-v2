from datetime import datetime,timedelta,timezone
import pytest
from services.broader_market_intelligence import evaluate_volatility_context
from tests.test_volatility_snapshot_v1 import make,NOW
def test_passes_regime_direction_and_strength():
 value=evaluate_volatility_context(volatility_snapshot=make(normalized_volatility_regime="HIGH",volatility_change_percent=5,previous_volatility_value=14.285714285714286,volatility_value=15),created_at=NOW,context_id="c")
 assert (value.volatility_regime,value.volatility_direction,value.volatility_strength)==("HIGH","RISING",.5)
def test_unavailable_stale_and_partial():
 assert evaluate_volatility_context(volatility_snapshot=make(volatility_value=None,normalized_volatility_regime="UNAVAILABLE"),created_at=NOW,context_id="c").context_status=="UNAVAILABLE"
 assert evaluate_volatility_context(volatility_snapshot=make(source_timestamp=NOW-timedelta(hours=1)),created_at=NOW,context_id="c").context_status=="UNAVAILABLE"
 assert evaluate_volatility_context(volatility_snapshot=make(is_partial=True),created_at=NOW,context_id="c").context_status=="BLOCKED"
def test_type_safety():
 with pytest.raises(TypeError):evaluate_volatility_context(volatility_snapshot={},created_at=NOW,context_id="c")
