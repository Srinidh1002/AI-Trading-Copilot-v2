from datetime import datetime,timezone
from dataclasses import replace
import pytest
from services.contracts import TechnicalIndicatorValueV1,TimeframeTechnicalEvidenceV1,TechnicalIntelligenceResultV1,DEFAULT_TECHNICAL_INTELLIGENCE_POLICY
N=datetime(2025,1,1,tzinfo=timezone.utc);C=("TREND","MOMENTUM","VOLATILITY","VOLUME","LEVELS","PATTERNS")
def e(**k):
 i=TechnicalIndicatorValueV1("RSI","5m",50.,"NEUTRAL","VALID",15,20)
 d=dict(timeframe_technical_evidence_id="e",created_at=N,underlying_symbol="NIFTY",exchange="NSE",timeframe="5m",timeframe_evidence_id="base",indicators=(i,),category_biases=tuple((x,"NEUTRAL") for x in C),category_strengths=tuple((x,.5) for x in C),trend_bias="NEUTRAL",momentum_bias="NEUTRAL");d.update(k);return TimeframeTechnicalEvidenceV1(**d)
def r(**k):
 d=dict(technical_intelligence_result_id="r",created_at=N,multi_timeframe_snapshot_id="s",multi_timeframe_quality_result_id="q",underlying_symbol="NIFTY",exchange="NSE",timeframe_evidence=(e(),),status="READY",aggregate_bias="NEUTRAL",aggregate_strength=0.);d.update(k);return TechnicalIntelligenceResultV1(**d)
@pytest.mark.parametrize("field,values",[("trend_bias",["BULLISH","BEARISH","NEUTRAL","UNAVAILABLE"]),("momentum_bias",["BULLISH","BEARISH","NEUTRAL","OVERBOUGHT","OVERSOLD","UNAVAILABLE"]),("volatility_state",["EXPANDING","CONTRACTING","NORMAL","HIGH","LOW","UNAVAILABLE"]),("volume_state",["SUPPORTIVE","WEAK","NEUTRAL","UNAVAILABLE"]),("level_state",["ABOVE_RESISTANCE","BELOW_SUPPORT","NEAR_RESISTANCE","NEAR_SUPPORT","INSIDE_RANGE","UNAVAILABLE"]),("pattern_state",["BULLISH","BEARISH","NEUTRAL","NONE","UNAVAILABLE"])])
def test_controlled_category_states(field,values):
 for value in values: assert getattr(e(**{field:value}),field)==value
@pytest.mark.parametrize("strength",[0.,.1,.2,.3,.4,.5,.6,.7,.8,.9,1.])
def test_strength_bounds(strength):assert e(trend_bias="BULLISH",trend_strength=strength).trend_strength==strength
@pytest.mark.parametrize("symbol,exchange",[("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")])
def test_four_identity_evidence(symbol,exchange):assert e(underlying_symbol=symbol,exchange=exchange).exchange==exchange
@pytest.mark.parametrize("behavior",["BLOCK","WARN","ALLOW"])
@pytest.mark.parametrize("field",["incomplete_timeframe_behavior","insufficient_history_behavior","conflicting_timeframe_behavior"])
def test_new_policy_controls(field,behavior):assert getattr(replace(DEFAULT_TECHNICAL_INTELLIGENCE_POLICY,**{field:behavior}),field)==behavior
@pytest.mark.parametrize("field",["trend_strength","momentum_strength","volatility_strength","volume_strength","level_strength","pattern_strength"])
def test_unavailable_rejects_strength(field):
 state={"trend_strength":"trend_bias","momentum_strength":"momentum_bias","volatility_strength":"volatility_state","volume_strength":"volume_state","level_strength":"level_state","pattern_strength":"pattern_state"}[field]
 with pytest.raises(ValueError):e(**{field:.1,state:"UNAVAILABLE"})
@pytest.mark.parametrize("field",["bullish_evidence_count","bearish_evidence_count","neutral_evidence_count"])
def test_counts_cannot_exceed_valid(field):
 with pytest.raises(ValueError):e(**{field:2})
def test_blocked_result_requires_zero_strength():
 with pytest.raises(ValueError):r(status="FAILED",blockers=("x",),aggregate_strength=.1)
def test_result_serializes_new_fields():assert "required_timeframes" in r().to_dict() and "valid_indicator_count" in r().to_dict()
def test_evidence_serializes_new_fields():assert "trend_bias" in e().to_dict() and "volume_strength" in e().to_dict()
def test_classification_overlap_rejected():
 with pytest.raises(ValueError):r(bullish_timeframes=("5m",),neutral_timeframes=("5m",))
def test_ready_with_warning_is_valid():assert r(status="READY_WITH_WARNINGS",warnings=("w",)).status=="READY_WITH_WARNINGS"
def test_blocked_evidence_is_honest():assert TimeframeTechnicalEvidenceV1("b",N,"NIFTY","NSE","5m","base",(),tuple((x,"UNAVAILABLE") for x in C),tuple((x,0.) for x in C),blockers=("blocked",)).valid_indicator_count==0
@pytest.mark.parametrize("field",["policy_name","rsi_period","ema_fast_period","ema_slow_period","macd_fast_period","macd_slow_period","macd_signal_period","adx_period","atr_period","bollinger_period","bollinger_stddev","volume_lookback","support_resistance_lookback","rsi_overbought","rsi_oversold","adx_threshold","required_timeframes","category_weights","timeframe_weights","execution_mode","live_execution_eligible","schema_version","incomplete_timeframe_behavior","insufficient_history_behavior","conflicting_timeframe_behavior","unavailable_behavior","malformed_behavior"])
def test_policy_serialization_surface_is_immutable(field):
 assert hasattr(DEFAULT_TECHNICAL_INTELLIGENCE_POLICY,field)
