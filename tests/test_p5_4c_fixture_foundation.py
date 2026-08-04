import pytest
from tests.fixtures.p5_4c import *
@pytest.mark.parametrize("symbol,exchange",CANONICAL_IDENTITIES)
@pytest.mark.parametrize("timeframe",REQUIRED_TIMEFRAMES)
@pytest.mark.parametrize("factory",[bullish_series,bearish_series,flat_series,breakout_series,breakdown_series,insufficient_history_series,incomplete_series])
def test_series_foundations(symbol,exchange,timeframe,factory):
 s=factory(symbol=symbol,exchange=exchange,timeframe=timeframe);assert s.underlying_symbol==symbol and all(a.start_at<b.start_at for a,b in zip(s.candles,s.candles[1:]))
@pytest.mark.parametrize("status",["READY","READY_WITH_WARNINGS","STALE","FUTURE","EMPTY","MALFORMED","UNSUPPORTED","FAILED"])
@pytest.mark.parametrize("timeframe",REQUIRED_TIMEFRAMES)
def test_evidence_states(status,timeframe):assert timeframe_evidence(bullish_series(timeframe=timeframe),status=status).quality_status==status
@pytest.mark.parametrize("kind",["bullish","bearish","neutral","unavailable"])
@pytest.mark.parametrize("timeframe",REQUIRED_TIMEFRAMES)
def test_technical_states(kind,timeframe):assert technical_evidence(timeframe,kind=kind).timeframe==timeframe
@pytest.mark.parametrize("status",["READY","READY_WITH_WARNINGS","MISSING_TIMEFRAMES","STALE","FUTURE","INCOMPLETE","INSUFFICIENT_HISTORY","MISALIGNED","MALFORMED","UNSUPPORTED","FAILED"])
def test_quality_states(status):assert quality_result(status=status).quality_status==status
@pytest.mark.parametrize("behavior",["BLOCK","WARN","ALLOW"])
def test_policies(behavior):assert policy_variant(incomplete=behavior).incomplete_timeframe_behavior==behavior
