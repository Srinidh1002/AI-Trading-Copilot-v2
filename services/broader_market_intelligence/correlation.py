"""Pure simple-return Pearson correlation for canonical completed candles."""
from __future__ import annotations
import math
from datetime import datetime
from services.contracts.broader_market_intelligence_policy_v1 import DEFAULT_BROADER_MARKET_INTELLIGENCE_POLICY, BroaderMarketIntelligencePolicyV1
from services.contracts.cross_market_evidence_v1 import CrossMarketEvidenceV1
from services.contracts.market_candle_series_v1 import MarketCandleSeriesV1
_NEUTRAL_RETURN_TOLERANCE=0.001
def _source_timestamp(series):
 values=[c.end_at for c in series.candles if c.is_complete]
 return values[-1] if values else series.created_at
def _state(value,policy):
 if value>=policy.strong_positive_correlation_threshold:return "STRONG_POSITIVE"
 if value>=policy.moderate_positive_correlation_threshold:return "MODERATE_POSITIVE"
 if value<=policy.strong_negative_correlation_threshold:return "STRONG_NEGATIVE"
 if value<=policy.moderate_negative_correlation_threshold:return "MODERATE_NEGATIVE"
 return "WEAK"
def _direction(closes):
 value=closes[-1]/closes[0]-1
 return "BULLISH" if value>_NEUTRAL_RETURN_TOLERANCE else "BEARISH" if value<-_NEUTRAL_RETURN_TOLERANCE else "NEUTRAL"
def _pearson(left,right):
 lx=sum(left)/len(left);rx=sum(right)/len(right);numerator=sum((a-lx)*(b-rx) for a,b in zip(left,right));a=sum((x-lx)**2 for x in left);b=sum((x-rx)**2 for x in right)
 if a==0 or b==0:return None
 value=numerator/math.sqrt(a*b)
 return max(-1.,min(1.,value)) if math.isfinite(value) else None
def _blocked(primary,related,policy,created_at,evidence_id,status,message):
 relationship="BROAD_MARKET" if {primary.underlying_symbol,related.underlying_symbol}=={"NIFTY","SENSEX"} else "FINANCIAL_INDEX"
 return CrossMarketEvidenceV1(evidence_id,created_at,primary.underlying_symbol,primary.exchange,related.underlying_symbol,related.exchange,relationship,primary.timeframe,policy.minimum_correlation_lookback,0,None,0.,"UNAVAILABLE","UNAVAILABLE","UNAVAILABLE","UNAVAILABLE","UNAVAILABLE",status,primary.series_id,related.series_id,_source_timestamp(primary),_source_timestamp(related),blockers=(message,))
def evaluate_cross_market_correlation(*,primary_series:MarketCandleSeriesV1,related_series:MarketCandleSeriesV1,policy:BroaderMarketIntelligencePolicyV1=DEFAULT_BROADER_MARKET_INTELLIGENCE_POLICY,created_at:datetime,evidence_id:str)->CrossMarketEvidenceV1:
 """Evaluate descriptive simple-return correlation without provider I/O."""
 if not isinstance(primary_series,MarketCandleSeriesV1) or not isinstance(related_series,MarketCandleSeriesV1):raise TypeError("series inputs must be MarketCandleSeriesV1")
 if not isinstance(policy,BroaderMarketIntelligencePolicyV1):raise TypeError("policy must be a BroaderMarketIntelligencePolicyV1")
 if not isinstance(created_at,datetime):raise TypeError("created_at must be a datetime")
 if created_at.tzinfo is None or created_at.utcoffset() is None:raise ValueError("created_at must be timezone-aware")
 if not isinstance(evidence_id,str) or not evidence_id.strip():raise ValueError("evidence_id must be non-empty")
 identity=(primary_series.underlying_symbol,primary_series.exchange);other=(related_series.underlying_symbol,related_series.exchange)
 if other not in policy.required_cross_market_relationships.get(identity,()):raise ValueError("series identities are not a configured canonical relationship")
 if policy.require_same_timeframe and primary_series.timeframe!=related_series.timeframe:return _blocked(primary_series,related_series,policy,created_at,evidence_id,"MISALIGNED","cross-market timeframes are misaligned")
 pt,rt=_source_timestamp(primary_series),_source_timestamp(related_series)
 if max((pt-created_at).total_seconds(),(rt-created_at).total_seconds())>policy.future_timestamp_tolerance_seconds:return _blocked(primary_series,related_series,policy,created_at,evidence_id,"BLOCKED","cross-market source timestamp exceeds future tolerance")
 if max((created_at-pt).total_seconds(),(created_at-rt).total_seconds())>policy.maximum_cross_market_age_seconds:return _blocked(primary_series,related_series,policy,created_at,evidence_id,"STALE","cross-market source evidence is stale")
 if abs((pt-rt).total_seconds())>policy.maximum_cross_market_timestamp_skew_seconds:return _blocked(primary_series,related_series,policy,created_at,evidence_id,"MISALIGNED","cross-market source timestamps exceed allowed skew")
 if not policy.allow_partial_candle_evidence and (any(not c.is_complete for c in primary_series.candles) or any(not c.is_complete for c in related_series.candles)):return _blocked(primary_series,related_series,policy,created_at,evidence_id,"BLOCKED","partial candle evidence is not allowed")
 p={c.start_at:c for c in primary_series.candles if c.is_complete or policy.allow_partial_candle_evidence};r={c.start_at:c for c in related_series.candles if c.is_complete or policy.allow_partial_candle_evidence};times=tuple(sorted(set(p)&set(r)))
 if len(times)<2:return _blocked(primary_series,related_series,policy,created_at,evidence_id,"INSUFFICIENT_DATA","insufficient aligned candles for returns")
 pc=tuple(p[t].close_price for t in times);rc=tuple(r[t].close_price for t in times);pr=tuple(b/a-1 for a,b in zip(pc,pc[1:]));rr=tuple(b/a-1 for a,b in zip(rc,rc[1:]))
 if len(pr)<policy.minimum_correlation_sample_size:return _blocked(primary_series,related_series,policy,created_at,evidence_id,"INSUFFICIENT_DATA","aligned return pair count is below policy minimum")
 value=_pearson(pr,rr)
 if value is None:return _blocked(primary_series,related_series,policy,created_at,evidence_id,"UNAVAILABLE","cross-market return variance is zero or invalid")
 dp,dr=_direction(pc),_direction(rc);positive=value>=policy.moderate_positive_correlation_threshold;opposite={dp,dr}=={"BULLISH","BEARISH"};strength=abs(value);confirmation="CONFIRMING" if positive and dp==dr and dp!="NEUTRAL" else "NOT_CONFIRMING" if positive and opposite else "PARTIAL";divergence="DIRECTIONAL_DIVERGENCE" if positive and opposite and strength>=policy.divergence_warning_strength else "NONE";warnings=("cross-market directional divergence is observed",) if divergence!="NONE" else ()
 if divergence!="NONE" and policy.block_on_strong_directional_divergence and strength>=policy.divergence_block_strength:return _blocked(primary_series,related_series,policy,created_at,evidence_id,"BLOCKED","strong directional divergence is blocked by policy")
 relationship="BROAD_MARKET" if {primary_series.underlying_symbol,related_series.underlying_symbol}=={"NIFTY","SENSEX"} else "FINANCIAL_INDEX"
 return CrossMarketEvidenceV1(evidence_id,created_at,primary_series.underlying_symbol,primary_series.exchange,related_series.underlying_symbol,related_series.exchange,relationship,primary_series.timeframe,len(pc),len(pr),value,strength,_state(value,policy),dp,dr,confirmation,divergence,"READY_WITH_WARNINGS" if warnings else "READY",primary_series.series_id,related_series.series_id,pt,rt,warnings=warnings)
