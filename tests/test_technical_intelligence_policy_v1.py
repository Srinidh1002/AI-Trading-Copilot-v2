from dataclasses import FrozenInstanceError, replace
import pytest
from services.contracts import TechnicalIntelligencePolicyV1,DEFAULT_TECHNICAL_INTELLIGENCE_POLICY

def test_default_policy_exact_values():
    p=DEFAULT_TECHNICAL_INTELLIGENCE_POLICY; assert (p.policy_name,p.required_timeframes,p.category_weights,p.timeframe_weights)==("INITIAL_CANONICAL_TECHNICAL_POLICY",("5m","15m","1h","1d"),(("TREND",.25),("MOMENTUM",.20),("VOLATILITY",.15),("VOLUME",.15),("LEVELS",.15),("PATTERNS",.10)),(("5m",.35),("15m",.30),("1h",.20),("1d",.15)))
@pytest.mark.parametrize("field",["rsi_period","ema_fast_period","ema_slow_period","macd_fast_period","macd_slow_period","macd_signal_period","adx_period","atr_period","bollinger_period","volume_lookback","support_resistance_lookback"])
@pytest.mark.parametrize("value",[0,-1,True])
def test_invalid_numeric_values_rejected(field,value):
    with pytest.raises(ValueError):replace(DEFAULT_TECHNICAL_INTELLIGENCE_POLICY,**{field:value})
@pytest.mark.parametrize("change",[{"required_timeframes":("5m",)},{"bollinger_stddev":1.},{"rsi_overbought":80},{"rsi_oversold":20},{"adx_threshold":20},{"category_weights":(("TREND",1.),)},{"timeframe_weights":(("5m",1.),)},{"insufficient_history_behavior":"IGNORE"},{"execution_mode":"LIVE"},{"live_execution_eligible":True}])
def test_policy_exactness_rejects_changes(change):
    with pytest.raises(ValueError):replace(DEFAULT_TECHNICAL_INTELLIGENCE_POLICY,**change)
@pytest.mark.parametrize("field",["insufficient_history_behavior","unavailable_behavior","malformed_behavior"])
@pytest.mark.parametrize("value",["BLOCK","WARN","ALLOW"])
def test_behaviors_are_controlled(field,value):assert replace(DEFAULT_TECHNICAL_INTELLIGENCE_POLICY,**{field:value}).__getattribute__(field)==value
def test_frozen():
    with pytest.raises(FrozenInstanceError):DEFAULT_TECHNICAL_INTELLIGENCE_POLICY.policy_name="x"
def test_policy_is_paper_only(): assert DEFAULT_TECHNICAL_INTELLIGENCE_POLICY.live_execution_eligible is False
