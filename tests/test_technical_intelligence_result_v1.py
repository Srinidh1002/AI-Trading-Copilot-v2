from datetime import datetime, timezone
from dataclasses import FrozenInstanceError
import pytest
from services.contracts import TechnicalIndicatorValueV1,TimeframeTechnicalEvidenceV1,TechnicalIntelligenceResultV1
NOW=datetime(2025,1,1,tzinfo=timezone.utc); C=("TREND","MOMENTUM","VOLATILITY","VOLUME","LEVELS","PATTERNS")
def evidence(timeframe="5m",symbol="NIFTY",exchange="NSE"):
    i=TechnicalIndicatorValueV1("RSI",timeframe,50.,"NEUTRAL","VALID",15,20)
    return TimeframeTechnicalEvidenceV1("e"+timeframe,NOW,symbol,exchange,timeframe,"base"+timeframe,(i,),tuple((x,"NEUTRAL") for x in C),tuple((x,.5) for x in C),trend_bias="NEUTRAL",momentum_bias="NEUTRAL")
def valid(**changes):
    data=dict(technical_intelligence_result_id="r",created_at=NOW,multi_timeframe_snapshot_id="s",multi_timeframe_quality_result_id="q",underlying_symbol="NIFTY",exchange="NSE",timeframe_evidence=(evidence(),),status="READY",aggregate_bias="NEUTRAL",aggregate_strength=.5)
    data.update(changes);return TechnicalIntelligenceResultV1(**data)
@pytest.mark.parametrize("symbol,exchange",[("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")])
@pytest.mark.parametrize("bias",["BULLISH","BEARISH","NEUTRAL","MIXED","UNAVAILABLE"])
def test_valid_ready_results(symbol,exchange,bias):assert valid(underlying_symbol=symbol,exchange=exchange,timeframe_evidence=(evidence(symbol=symbol,exchange=exchange),),aggregate_bias=bias).aggregate_bias==bias
@pytest.mark.parametrize("status",["MISSING_TIMEFRAMES","STALE","FUTURE","INCOMPLETE","INSUFFICIENT_HISTORY","CONFLICTING","MALFORMED","UNSUPPORTED","FAILED"])
def test_blocked_status_requires_blocker(status):assert valid(status=status,blockers=("blocked",),aggregate_strength=0.).status==status
@pytest.mark.parametrize("change",[{"status":"UNKNOWN","blockers":("x",)},{"aggregate_bias":"BUY"},{"aggregate_strength":-0.1},{"aggregate_strength":1.1},{"execution_mode":"LIVE"},{"live_execution_eligible":True},{"underlying_symbol":"NIFTY","exchange":"BSE"},{"timeframe_evidence":(evidence(),evidence())}])
def test_invalid_result_rejected(change):
    with pytest.raises(ValueError):valid(**change)
def test_warning_state_needs_warning():assert valid(status="READY_WITH_WARNINGS",warnings=("late",)).status=="READY_WITH_WARNINGS"
def test_warning_state_rejects_blocker():
    with pytest.raises(ValueError):valid(status="READY_WITH_WARNINGS",warnings=("x",),blockers=("y",))
def test_nonready_needs_blocker():
    with pytest.raises(ValueError):valid(status="FAILED")
def test_serialization_is_deterministic():assert valid().to_dict()==valid().to_dict()
def test_frozen():
    with pytest.raises(FrozenInstanceError):valid().status="FAILED"

@pytest.mark.parametrize("strength",[0.,.1,.2,.3,.4,.5,.6,.7,.8,.9,1.])
def test_aggregate_strength_boundaries(strength):
    assert valid(aggregate_strength=strength).aggregate_strength == strength
@pytest.mark.parametrize("timeframes",[("5m",),("5m","15m"),("5m","15m","1h")])
def test_evidence_timeframe_order_is_canonical(timeframes):
    values=tuple(evidence(timeframe) for timeframe in timeframes)
    assert valid(timeframe_evidence=values).timeframe_evidence == values
