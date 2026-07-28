from services.contracts.multi_timeframe_policy_v1 import DEFAULT_MULTI_TIMEFRAME_POLICY
def timeframe_duration_seconds(timeframe):return {"1m":60,"3m":180,"5m":300,"15m":900,"30m":1800,"1h":3600,"1d":86400}[timeframe]
def get_latest_complete_candle_end(series):
 values=[c.end_at for c in series.candles if c.is_complete];return values[-1] if values else None
def evaluate_timeframe_alignment(timeframe_evidence,*,policy=DEFAULT_MULTI_TIMEFRAME_POLICY):
 values=tuple(timeframe_evidence);anchor=next((v for v in values if v.timeframe==policy.anchor_timeframe),None);reference=anchor.latest_complete_candle_end_at if anchor else None
 if reference is None:return None,(),None,("anchor_timeframe_unavailable",),()
 bad=[];gaps=[]
 for v in values:
  if v.latest_complete_candle_end_at is not None:
   gap=abs((v.latest_complete_candle_end_at-reference).total_seconds());gaps.append(gap)
   if gap>dict(policy.maximum_alignment_gap_seconds_by_timeframe)[v.timeframe]:bad.append(v.timeframe)
 return reference,tuple(bad),max(gaps) if gaps else None,("timeframes_misaligned",) if bad else (),()
