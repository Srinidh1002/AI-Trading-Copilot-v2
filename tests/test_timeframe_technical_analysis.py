from services.contracts import TechnicalIndicatorValueV1
from services.technical_intelligence import analyze_timeframe_technical_evidence
from tests.fixtures.p5_4c import bullish_series,timeframe_evidence
from tests.fixtures.p5_4c import CANONICAL_IDENTITIES,REQUIRED_TIMEFRAMES,default_policy,policy_variant,incomplete_series
import pytest

def _result(category, indicators=(), bias="NEUTRAL", strength=0.):
    return {"category":category,"bias":bias,"strength":strength,"indicators":indicators,"blockers":(),"warnings":()}
def _patch_categories(monkeypatch, volume_signals):
    import services.technical_intelligence.trend as trend,services.technical_intelligence.momentum as momentum,services.technical_intelligence.volatility as volatility,services.technical_intelligence.levels as levels,services.technical_intelligence.patterns as patterns
    def indicator(name, signal): return TechnicalIndicatorValueV1(name,"5m",1.,signal,"VALID",1,60)
    monkeypatch.setattr(trend,"evaluate_trend_intelligence",lambda s,p:_result("TREND",(indicator("TREND_I","BULLISH"),),"BULLISH",.5))
    monkeypatch.setattr(momentum,"evaluate_momentum_intelligence",lambda s,p:_result("MOMENTUM",()))
    monkeypatch.setattr(volatility,"evaluate_volatility_intelligence",lambda s,p:_result("VOLATILITY",tuple(indicator(name,signal) for name,signal in volume_signals),"NEUTRAL",.5))
    monkeypatch.setattr(levels,"evaluate_level_intelligence",lambda s,p:_result("LEVELS",()))
    monkeypatch.setattr(patterns,"evaluate_pattern_intelligence",lambda s,p:_result("PATTERNS",()))
def _analyze(monkeypatch, signals):
    _patch_categories(monkeypatch,signals);s=bullish_series();return analyze_timeframe_technical_evidence(candle_series=s,timeframe_evidence=timeframe_evidence(s),clock=lambda:timeframe_evidence(s).created_at)
def test_supportive_volume_state_projects_legacy_neutral(monkeypatch):
    value=_analyze(monkeypatch,(("VOLUME_AVERAGE","HIGH"),("VWAP","BULLISH")));assert value.volume_state=="SUPPORTIVE" and dict(value.category_biases)["VOLUME"]=="NEUTRAL"
def test_weak_volume_state_projects_legacy_neutral(monkeypatch):
    value=_analyze(monkeypatch,(("VOLUME_AVERAGE","LOW"),("VWAP","BEARISH")));assert value.volume_state=="WEAK" and dict(value.category_biases)["VOLUME"]=="NEUTRAL"
def test_unavailable_volume_projects_legacy_unavailable(monkeypatch):
    value=_analyze(monkeypatch,(("VOLUME_AVERAGE","HIGH"),));assert value.volume_state=="UNAVAILABLE" and dict(value.category_biases)["VOLUME"]=="UNAVAILABLE" and value.volume_strength==0.
def test_volume_projection_preserves_serialized_detailed_state(monkeypatch):
    value=_analyze(monkeypatch,(("VOLUME_AVERAGE","HIGH"),("VWAP","BULLISH")));assert value.to_dict()["volume_state"]=="SUPPORTIVE" and value.to_dict()["category_biases"][3]==["VOLUME","NEUTRAL"]
def test_volume_projection_does_not_add_directional_counts(monkeypatch):
    supportive=_analyze(monkeypatch,(("VOLUME_AVERAGE","HIGH"),("VWAP","BULLISH")));weak=_analyze(monkeypatch,(("VOLUME_AVERAGE","LOW"),("VWAP","BEARISH")));assert dict(supportive.category_biases)["VOLUME"]==dict(weak.category_biases)["VOLUME"]=="NEUTRAL" and supportive.valid_indicator_count==weak.valid_indicator_count

@pytest.mark.parametrize("symbol,exchange",CANONICAL_IDENTITIES)
@pytest.mark.parametrize("timeframe",REQUIRED_TIMEFRAMES)
def test_usable_identity_timeframe_matrix(symbol,exchange,timeframe):
    series=bullish_series(symbol=symbol,exchange=exchange,timeframe=timeframe);evidence=timeframe_evidence(series)
    result=analyze_timeframe_technical_evidence(candle_series=series,timeframe_evidence=evidence,clock=lambda:evidence.created_at,timeframe_technical_evidence_id_factory=lambda:"id-"+timeframe)
    assert (result.underlying_symbol,result.exchange,result.timeframe,result.timeframe_evidence_id)==(symbol,exchange,timeframe,evidence.timeframe_evidence_id)

@pytest.mark.parametrize("status",["STALE","FUTURE","EMPTY","MALFORMED","UNSUPPORTED","FAILED"])
@pytest.mark.parametrize("symbol,exchange",CANONICAL_IDENTITIES)
@pytest.mark.parametrize("timeframe",REQUIRED_TIMEFRAMES)
def test_blocking_quality_matrix_returns_empty_unavailable_evidence(status,symbol,exchange,timeframe):
    series=bullish_series(symbol=symbol,exchange=exchange,timeframe=timeframe);evidence=timeframe_evidence(series,status=status)
    result=analyze_timeframe_technical_evidence(candle_series=series,timeframe_evidence=evidence,clock=lambda:evidence.created_at)
    assert result.indicators==() and result.valid_indicator_count==result.unavailable_indicator_count==0
    assert (result.trend_bias,result.momentum_bias,result.volatility_state,result.volume_state,result.level_state,result.pattern_state)==("UNAVAILABLE",)*6

@pytest.mark.parametrize("bad_series,bad_evidence",[("series",None),(None,"evidence")])
def test_primary_type_validation_precedes_clock(bad_series,bad_evidence):
    series=bullish_series();evidence=timeframe_evidence(series);calls=[]
    with pytest.raises(ValueError):analyze_timeframe_technical_evidence(candle_series=series if bad_series is None else bad_series,timeframe_evidence=evidence if bad_evidence is None else bad_evidence,clock=lambda:calls.append(1))
    assert not calls

@pytest.mark.parametrize("field",["series_id","underlying_symbol","exchange","timeframe"])
def test_exact_series_evidence_linkage(field):
    series=bullish_series();evidence=timeframe_evidence(series);changes={field:"bad"}
    if field=="series_id": evidence=timeframe_evidence(series,candle_series_id="bad")
    elif field=="underlying_symbol": evidence=timeframe_evidence(series,underlying_symbol="SENSEX",exchange="BSE")
    elif field=="exchange": evidence=timeframe_evidence(bullish_series(symbol="SENSEX",exchange="BSE"))
    else: evidence=timeframe_evidence(series,timeframe="15m")
    with pytest.raises(ValueError):analyze_timeframe_technical_evidence(candle_series=series,timeframe_evidence=evidence)

@pytest.mark.parametrize("value",["", "   ", 1])
def test_invalid_factory_ids_are_rejected(value):
    series=bullish_series();evidence=timeframe_evidence(series)
    with pytest.raises(ValueError):analyze_timeframe_technical_evidence(candle_series=series,timeframe_evidence=evidence,clock=lambda:evidence.created_at,timeframe_technical_evidence_id_factory=lambda:value)

def test_clock_called_once_and_fixed_id_preserved():
    series=bullish_series();evidence=timeframe_evidence(series);calls=[]
    result=analyze_timeframe_technical_evidence(candle_series=series,timeframe_evidence=evidence,clock=lambda:(calls.append(1) or evidence.created_at),timeframe_technical_evidence_id_factory=lambda:"fixed")
    assert calls==[1] and (result.created_at,result.timeframe_technical_evidence_id)==(evidence.created_at,"fixed")

@pytest.mark.parametrize("behavior",["BLOCK","WARN","ALLOW"])
def test_incomplete_behavior_is_policy_controlled(behavior):
    series=incomplete_series();evidence=timeframe_evidence(series,latest_candle_complete=False)
    result=analyze_timeframe_technical_evidence(candle_series=series,timeframe_evidence=evidence,policy=policy_variant(incomplete=behavior),clock=lambda:evidence.created_at)
    assert (result.indicators==()) is (behavior=="BLOCK")
