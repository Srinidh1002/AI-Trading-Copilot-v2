import itertools
import pytest
from tests.fixtures.p5_4c import CANONICAL_IDENTITIES,snapshot,quality_result,bullish_series,REQUIRED_TIMEFRAMES
from services.technical_intelligence import build_canonical_technical_intelligence

STATUSES=("READY","READY_WITH_WARNINGS","FAILED","UNSUPPORTED","MALFORMED","FUTURE","MISSING_TIMEFRAMES","STALE","INCOMPLETE","INSUFFICIENT_HISTORY")
BLOCKING=set(STATUSES)-{"READY","READY_WITH_WARNINGS"}
ORDERS=(REQUIRED_TIMEFRAMES,tuple(reversed(REQUIRED_TIMEFRAMES)),("15m","1d","5m","1h"))
def series_for(snap,order):
 by_time={e.timeframe:bullish_series(symbol=snap.underlying_symbol,exchange=snap.exchange,timeframe=e.timeframe,series_id=e.candle_series_id) for e in snap.timeframe_evidence}
 return tuple(by_time[t] for t in order)

@pytest.mark.parametrize("symbol,exchange",CANONICAL_IDENTITIES)
@pytest.mark.parametrize("order",ORDERS)
@pytest.mark.parametrize("status",STATUSES)
def test_identity_order_quality_matrix(symbol,exchange,order,status):
 snap=snapshot(symbol,exchange);quality=quality_result(snap,status=status)
 result=build_canonical_technical_intelligence(candle_series_by_timeframe=series_for(snap,order),multi_timeframe_snapshot=snap,multi_timeframe_quality_result=quality,clock=lambda:snap.created_at)
 if status in BLOCKING: assert result.status==status and result.aggregate_strength==0.
 else: assert result.status in {"READY","READY_WITH_WARNINGS"} and tuple(x.timeframe for x in result.timeframe_evidence)==REQUIRED_TIMEFRAMES

@pytest.mark.parametrize("bad",[[],(),("bad",)])
def test_tuple_member_validation(bad):
 snap=snapshot();quality=quality_result(snap)
 with pytest.raises(ValueError):build_canonical_technical_intelligence(candle_series_by_timeframe=bad,multi_timeframe_snapshot=snap,multi_timeframe_quality_result=quality)

def test_one_clock_and_ordered_factories():
 snap=snapshot();quality=quality_result(snap);clocks=[];ids=[];results=[]
 result=build_canonical_technical_intelligence(candle_series_by_timeframe=series_for(snap,ORDERS[1]),multi_timeframe_snapshot=snap,multi_timeframe_quality_result=quality,clock=lambda:(clocks.append(1) or snap.created_at),timeframe_technical_evidence_id_factory=lambda:(ids.append(len(ids)) or f"t-{len(ids)}"),technical_intelligence_result_id_factory=lambda:(results.append(1) or "result"))
 assert clocks==[1] and ids==[0,1,2,3] and results==[1] and result.technical_intelligence_result_id=="result" and all(x.created_at==snap.created_at for x in result.timeframe_evidence)

def test_invalid_primary_input_does_not_consume_clock():
 snap=snapshot();calls=[]
 with pytest.raises(ValueError):build_canonical_technical_intelligence(candle_series_by_timeframe=(),multi_timeframe_snapshot=snap,multi_timeframe_quality_result=quality_result(snap),clock=lambda:calls.append(1))
 assert not calls
