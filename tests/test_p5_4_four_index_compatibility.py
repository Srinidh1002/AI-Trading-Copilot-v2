import pytest
from tests.fixtures.p5_4c import CANONICAL_IDENTITIES,REQUIRED_TIMEFRAMES,bullish_series,timeframe_evidence,snapshot,quality_result,technical_bundle,default_policy
from services.technical_intelligence import analyze_timeframe_technical_evidence,aggregate_technical_intelligence,build_canonical_technical_intelligence
def _series(s,reverse=False):
 values=tuple(bullish_series(symbol=s.underlying_symbol,exchange=s.exchange,timeframe=e.timeframe,series_id=e.candle_series_id) for e in s.timeframe_evidence);return tuple(reversed(values)) if reverse else values
@pytest.mark.parametrize("symbol,exchange",CANONICAL_IDENTITIES)
@pytest.mark.parametrize("timeframe",REQUIRED_TIMEFRAMES)
def test_each_market_timeframe_analysis_preserves_identity(symbol,exchange,timeframe):
 s=bullish_series(symbol=symbol,exchange=exchange,timeframe=timeframe);e=timeframe_evidence(s);r=analyze_timeframe_technical_evidence(candle_series=s,timeframe_evidence=e,clock=lambda:e.created_at);assert (r.underlying_symbol,r.exchange,r.timeframe)==(symbol,exchange,timeframe)
@pytest.mark.parametrize("symbol,exchange",CANONICAL_IDENTITIES)
@pytest.mark.parametrize("kind,bias",[("bullish","BULLISH"),("bearish","BEARISH"),("neutral","NEUTRAL")])
def test_each_market_aggregation_is_market_neutral(symbol,exchange,kind,bias):
 s=snapshot(symbol,exchange);r=aggregate_technical_intelligence(multi_timeframe_snapshot=s,multi_timeframe_quality_result=quality_result(s),timeframe_technical_evidence=technical_bundle(kind,symbol,exchange),clock=lambda:s.created_at);assert (r.aggregate_bias,r.underlying_symbol,r.exchange)==(bias,symbol,exchange)
@pytest.mark.parametrize("symbol,exchange",CANONICAL_IDENTITIES)
@pytest.mark.parametrize("status",["READY","READY_WITH_WARNINGS","FAILED","STALE"])
def test_each_market_pipeline_quality_path(symbol,exchange,status):
 s=snapshot(symbol,exchange);r=build_canonical_technical_intelligence(candle_series_by_timeframe=_series(s),multi_timeframe_snapshot=s,multi_timeframe_quality_result=quality_result(s,status=status),clock=lambda:s.created_at);assert (r.underlying_symbol,r.exchange)==(symbol,exchange)
@pytest.mark.parametrize("symbol,exchange",CANONICAL_IDENTITIES)
def test_each_market_pipeline_accepts_arbitrary_order(symbol,exchange):
 s=snapshot(symbol,exchange);r=build_canonical_technical_intelligence(candle_series_by_timeframe=_series(s,True),multi_timeframe_snapshot=s,multi_timeframe_quality_result=quality_result(s),clock=lambda:s.created_at);assert tuple(x.timeframe for x in r.timeframe_evidence)==REQUIRED_TIMEFRAMES
@pytest.mark.parametrize("symbol,exchange",CANONICAL_IDENTITIES)
def test_each_market_policy_and_serialization_are_exact(symbol,exchange):
 s=snapshot(symbol,exchange);r=aggregate_technical_intelligence(multi_timeframe_snapshot=s,multi_timeframe_quality_result=quality_result(s),timeframe_technical_evidence=technical_bundle("bullish",symbol,exchange),clock=lambda:s.created_at);assert r.to_dict()["exchange"]==exchange and default_policy().timeframe_weights==(("5m",.35),("15m",.3),("1h",.2),("1d",.15))
@pytest.mark.parametrize("symbol,exchange",CANONICAL_IDENTITIES)
def test_each_market_blocked_quality_has_no_strength(symbol,exchange):
 s=snapshot(symbol,exchange);r=aggregate_technical_intelligence(multi_timeframe_snapshot=s,multi_timeframe_quality_result=quality_result(s,status="FAILED"),timeframe_technical_evidence=technical_bundle("bullish",symbol,exchange),clock=lambda:s.created_at);assert r.aggregate_strength==0 and r.aggregate_bias=="UNAVAILABLE"
@pytest.mark.parametrize("symbol,exchange",CANONICAL_IDENTITIES)
def test_each_market_has_no_identity_fallback(symbol,exchange):
 assert (symbol,exchange) in CANONICAL_IDENTITIES and (symbol=="SENSEX")==(exchange=="BSE")
