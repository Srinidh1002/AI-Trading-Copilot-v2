from datetime import datetime,timezone
from services.contracts.market_data_freshness_policy_v1 import DEFAULT_MARKET_DATA_FRESHNESS_POLICY
from services.contracts.market_data_quality_result_v1 import MarketDataQualityResultV1
def evaluate_timestamp_freshness(*,observed_at,received_at,now,max_age_seconds,future_tolerance_seconds,clock_skew_tolerance_seconds):
 if not all(isinstance(v,datetime) and v.tzinfo for v in (observed_at,received_at,now)):return "MALFORMED",0,("naive_timestamp",),()
 if received_at<observed_at:return "MALFORMED",0,("received_before_observed",),()
 age=(now-observed_at).total_seconds()
 if age < -future_tolerance_seconds:return "FUTURE",age,("future_evidence",),()
 if age>max_age_seconds:return "STALE",age,("stale_evidence",),()
 return "VALID",age,(),()
def _result(subject,obj,policy,clock,factory,threshold):
 now=(clock or (lambda:datetime.now(timezone.utc)))();status,age,b,w=evaluate_timestamp_freshness(observed_at=getattr(obj,"observed_at",getattr(obj,"end_at",None)),received_at=getattr(obj,"received_at",getattr(obj,"end_at",None)),now=now,max_age_seconds=threshold,future_tolerance_seconds=policy.future_tolerance_seconds,clock_skew_tolerance_seconds=policy.provider_clock_skew_tolerance_seconds)
 return MarketDataQualityResultV1((factory or (lambda:"quality"))(),now,subject,status,getattr(obj,"underlying_symbol",None),getattr(obj,"exchange",None),getattr(obj,"timeframe",None),getattr(getattr(obj,"provenance",None),"provider",None),getattr(obj,"observed_at",getattr(obj,"end_at",None)),getattr(obj,"received_at",getattr(obj,"end_at",None)),age,threshold,1,1 if status=="VALID" else 0,0 if status=="VALID" else 1,blockers=b,warnings=w)
def evaluate_quote_freshness(quote,*,policy=DEFAULT_MARKET_DATA_FRESHNESS_POLICY,clock=None,quality_result_id_factory=None):return _result("QUOTE",quote,policy,clock,quality_result_id_factory,policy.quote_max_age_seconds)
def evaluate_candle_freshness(candle,*,policy=DEFAULT_MARKET_DATA_FRESHNESS_POLICY,clock=None,quality_result_id_factory=None):return _result("CANDLE",candle,policy,clock,quality_result_id_factory,dict(policy.candle_max_age_by_timeframe)[candle.timeframe])
