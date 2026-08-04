import pytest
from tests.fixtures.p5_4c import CANONICAL_IDENTITIES,snapshot,quality_result,technical_bundle,default_policy,policy_variant
from services.technical_intelligence import aggregate_technical_intelligence

BLOCKING={"FAILED","UNSUPPORTED","MALFORMED","FUTURE","MISSING_TIMEFRAMES","STALE","INCOMPLETE","INSUFFICIENT_HISTORY"}

@pytest.mark.parametrize("symbol,exchange",CANONICAL_IDENTITIES)
@pytest.mark.parametrize("kind,expected_bias",[("bullish","BULLISH"),("bearish","BEARISH"),("neutral","NEUTRAL")])
@pytest.mark.parametrize("status",["READY","READY_WITH_WARNINGS","FAILED","UNSUPPORTED","MALFORMED","FUTURE","MISSING_TIMEFRAMES","STALE","INCOMPLETE","INSUFFICIENT_HISTORY"])
def test_identity_direction_quality_matrix(symbol,exchange,kind,expected_bias,status):
    snap=snapshot(symbol,exchange);quality=quality_result(snap,status=status)
    result=aggregate_technical_intelligence(multi_timeframe_snapshot=snap,multi_timeframe_quality_result=quality,timeframe_technical_evidence=technical_bundle(kind,symbol,exchange),clock=lambda:snap.created_at)
    if status in BLOCKING:
        assert result.status==status and result.aggregate_bias=="UNAVAILABLE" and result.aggregate_strength==0.
    elif status=="READY_WITH_WARNINGS": assert result.status=="READY_WITH_WARNINGS" and result.aggregate_bias==expected_bias
    else: assert result.status=="READY" and result.aggregate_bias==expected_bias

@pytest.mark.parametrize("bad_snapshot,bad_quality,bad_evidence",[("snapshot",None,None),(None,"quality",None),(None,None,[])])
def test_primary_type_validation(bad_snapshot,bad_quality,bad_evidence):
    snap=snapshot();quality=quality_result(snap);evidence=technical_bundle("bullish")
    with pytest.raises(ValueError):aggregate_technical_intelligence(multi_timeframe_snapshot=snap if bad_snapshot is None else bad_snapshot,multi_timeframe_quality_result=quality if bad_quality is None else bad_quality,timeframe_technical_evidence=evidence if bad_evidence is None else bad_evidence)

@pytest.mark.parametrize("value",["", " ", 1])
def test_invalid_result_id_rejected(value):
    snap=snapshot();quality=quality_result(snap)
    with pytest.raises(ValueError):aggregate_technical_intelligence(multi_timeframe_snapshot=snap,multi_timeframe_quality_result=quality,timeframe_technical_evidence=technical_bundle("bullish"),clock=lambda:snap.created_at,technical_intelligence_result_id_factory=lambda:value)

def test_clock_once_and_weighted_bullish_score():
    snap=snapshot();quality=quality_result(snap);calls=[]
    result=aggregate_technical_intelligence(multi_timeframe_snapshot=snap,multi_timeframe_quality_result=quality,timeframe_technical_evidence=technical_bundle("bullish"),clock=lambda:(calls.append(1) or snap.created_at),technical_intelligence_result_id_factory=lambda:"result")
    assert calls==[1] and result.technical_intelligence_result_id=="result" and result.aggregate_strength==pytest.approx(.44)

def test_misaligned_warn_is_controlled_warning_path():
    snap=snapshot();quality=quality_result(snap,status="MISALIGNED")
    result=aggregate_technical_intelligence(multi_timeframe_snapshot=snap,multi_timeframe_quality_result=quality,timeframe_technical_evidence=technical_bundle("bullish"),clock=lambda:snap.created_at)
    assert result.status=="READY_WITH_WARNINGS"
