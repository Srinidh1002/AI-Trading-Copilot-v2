"""Pure pass-through evaluation of adapter-normalized volatility regimes."""
from __future__ import annotations
from datetime import datetime
from services.contracts.volatility_snapshot_v1 import VolatilitySnapshotV1
from services.contracts.volatility_context_v1 import VolatilityContextV1
from services.contracts.broader_market_intelligence_policy_v1 import DEFAULT_BROADER_MARKET_INTELLIGENCE_POLICY,BroaderMarketIntelligencePolicyV1
def _bad(s,p,now,context_id,status,message):
 return VolatilityContextV1(context_id,now,s.underlying_symbol,s.exchange,s.volatility_symbol,s.volatility_exchange,s.source_id,s.source_timestamp,None,None,"UNAVAILABLE","UNAVAILABLE",0.,status,blockers=(message,),warnings=s.warnings)
def evaluate_volatility_context(*,volatility_snapshot:VolatilitySnapshotV1,policy:BroaderMarketIntelligencePolicyV1=DEFAULT_BROADER_MARKET_INTELLIGENCE_POLICY,created_at:datetime,context_id:str)->VolatilityContextV1:
 if not isinstance(volatility_snapshot,VolatilitySnapshotV1):raise TypeError("volatility_snapshot must be a VolatilitySnapshotV1")
 if not isinstance(policy,BroaderMarketIntelligencePolicyV1):raise TypeError("policy must be a BroaderMarketIntelligencePolicyV1")
 if not isinstance(created_at,datetime):raise TypeError("created_at must be a datetime")
 if created_at.tzinfo is None or created_at.utcoffset() is None:raise ValueError("created_at must be timezone-aware")
 if not isinstance(context_id,str) or not context_id.strip():raise ValueError("context_id must be non-empty")
 age=(created_at-volatility_snapshot.source_timestamp).total_seconds()
 if age>policy.maximum_volatility_age_seconds:return _bad(volatility_snapshot,policy,created_at,context_id,"STALE" if policy.require_volatility_context else "UNAVAILABLE","volatility source evidence is stale")
 if age < -policy.future_timestamp_tolerance_seconds:return _bad(volatility_snapshot,policy,created_at,context_id,"BLOCKED","volatility source timestamp exceeds future tolerance")
 if volatility_snapshot.is_partial:return _bad(volatility_snapshot,policy,created_at,context_id,"BLOCKED","volatility snapshot is partial")
 if volatility_snapshot.blockers:return _bad(volatility_snapshot,policy,created_at,context_id,"BLOCKED","; ".join(volatility_snapshot.blockers))
 if volatility_snapshot.volatility_value is None or volatility_snapshot.normalized_volatility_regime=="UNAVAILABLE":return _bad(volatility_snapshot,policy,created_at,context_id,"BLOCKED" if policy.require_volatility_context else "UNAVAILABLE","volatility context is unavailable")
 change=volatility_snapshot.volatility_change_percent;direction="UNAVAILABLE" if change is None else "RISING" if change>.1 else "FALLING" if change<-.1 else "STABLE";strength=0. if change is None else min(abs(change)/10.,1.);warnings=list(volatility_snapshot.warnings)
 if volatility_snapshot.normalized_volatility_regime in {"HIGH","EXTREME"} and policy.warn_on_high_volatility:warnings.append("normalized volatility regime is high")
 if volatility_snapshot.normalized_volatility_regime=="EXTREME" and policy.block_on_extreme_volatility:return _bad(volatility_snapshot,policy,created_at,context_id,"BLOCKED","normalized volatility regime is extreme")
 if direction=="RISING" and policy.reduce_confidence_on_rising_volatility:warnings.append("normalized volatility is rising")
 return VolatilityContextV1(context_id,created_at,volatility_snapshot.underlying_symbol,volatility_snapshot.exchange,volatility_snapshot.volatility_symbol,volatility_snapshot.volatility_exchange,volatility_snapshot.source_id,volatility_snapshot.source_timestamp,volatility_snapshot.volatility_value,change,volatility_snapshot.normalized_volatility_regime,direction,strength,"READY_WITH_WARNINGS" if warnings else "READY",warnings=tuple(dict.fromkeys(warnings)))
