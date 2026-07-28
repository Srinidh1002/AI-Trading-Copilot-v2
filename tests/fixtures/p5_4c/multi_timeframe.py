from tests.fixtures.p5_4c.market_series import BASE_TIME,REQUIRED_TIMEFRAMES,bullish_series
from tests.fixtures.p5_4c.timeframe_evidence import timeframe_evidence
from services.contracts import MultiTimeframeSnapshotV1,MultiTimeframeQualityResultV1
def snapshot(symbol="NIFTY",exchange="NSE",status="READY"):
 evidence=tuple(timeframe_evidence(bullish_series(symbol=symbol,exchange=exchange,timeframe=t,series_id="s-"+t),status="READY") for t in REQUIRED_TIMEFRAMES);return MultiTimeframeSnapshotV1("snapshot-"+symbol,BASE_TIME,symbol,exchange,REQUIRED_TIMEFRAMES,evidence,"5m",BASE_TIME)
def quality_result(s=None,status="READY",blockers=(),warnings=()):
 s=s or snapshot();bad=status not in {"READY","READY_WITH_WARNINGS"};return MultiTimeframeQualityResultV1("quality-"+s.multi_timeframe_snapshot_id,BASE_TIME,s.multi_timeframe_snapshot_id,status,s.underlying_symbol,s.exchange,REQUIRED_TIMEFRAMES,REQUIRED_TIMEFRAMES,(),(),(),(),(),(),4,4,BASE_TIME,0.,blockers or (("quality_"+status.lower(),) if bad else ()),warnings or (("warning",) if status=="READY_WITH_WARNINGS" else ()))
