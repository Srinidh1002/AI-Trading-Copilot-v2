"""Pure scheduled-event risk evaluator; calendar ownership stays external."""
from __future__ import annotations
from datetime import datetime
from services.contracts.external_context_policy_v1 import DEFAULT_EXTERNAL_CONTEXT_POLICY,ExternalContextPolicyV1
from services.contracts.scheduled_market_event_v1 import ScheduledMarketEventV1
from services.contracts.event_risk_context_result_v1 import EventRiskContextResultV1
from services.core.market_identity import normalize_market_identity
_R={"UNAVAILABLE":0,"LOW":1,"MODERATE":2,"HIGH":3,"EXTREME":4}
def _m(x):return tuple(sorted({" ".join(v.upper().split()) for v in x if v}))
def evaluate_event_risk_context(*,underlying_symbol:str,exchange:str,events:tuple[ScheduledMarketEventV1,...],policy:ExternalContextPolicyV1=DEFAULT_EXTERNAL_CONTEXT_POLICY,created_at:datetime,result_id:str)->EventRiskContextResultV1:
 i=normalize_market_identity(underlying_symbol,exchange)
 if i is None:raise ValueError("unsupported market identity")
 if not isinstance(events,tuple) or any(not isinstance(e,ScheduledMarketEventV1) for e in events):raise TypeError("events must be tuple ScheduledMarketEventV1")
 if not isinstance(policy,ExternalContextPolicyV1):raise TypeError("policy must be ExternalContextPolicyV1")
 if not isinstance(created_at,datetime) or created_at.tzinfo is None or created_at.utcoffset() is None:raise ValueError("created_at must be timezone-aware")
 if not isinstance(result_id,str) or not result_id.strip():raise ValueError("result_id required")
 if len({e.scheduled_market_event_id for e in events})!=len(events):raise ValueError("duplicate event ids")
 if any((e.affected_market_identities and i not in e.affected_market_identities) or (e.affected_exchanges and i[1] not in e.affected_exchanges) for e in events):raise ValueError("event does not apply")
 ev=tuple(sorted(events,key=lambda e:e.scheduled_market_event_id));w=[];b=[];support=[];active=[];upcoming=[];cool=[];blocking=[];warn=0;session=False;high="UNAVAILABLE"
 for e in ev:
  age=(created_at-e.source_timestamp).total_seconds()
  if age>policy.maximum_event_source_age_seconds or age < -policy.maximum_event_timestamp_skew_seconds:
   (b if policy.block_on_stale_event_calendar else w).append(f"EVENT CALENDAR SOURCE IS STALE FOR {e.scheduled_market_event_id}");continue
  if e.event_status=="BLOCKED":b.extend(e.blockers);continue
  if e.event_status in {"CANCELLED","UNAVAILABLE"}:continue
  end=e.scheduled_end or e.scheduled_start;kind=None
  if e.event_status=="ACTIVE" or e.scheduled_start<=created_at<=end:kind="ACTIVE";active.append(e.scheduled_market_event_id)
  elif created_at<e.scheduled_start and (e.scheduled_start-created_at).total_seconds()<=policy.event_lead_seconds_by_category.get(e.event_category,0):kind="UPCOMING";upcoming.append(e.scheduled_market_event_id)
  elif created_at>end and (created_at-end).total_seconds()<=policy.event_cooldown_seconds_by_category.get(e.event_category,0):kind="COOLDOWN";cool.append(e.scheduled_market_event_id)
  if not kind:continue
  high=max((high,e.severity),key=lambda x:_R[x]);support.append(f"{e.event_category} EVENT IS {kind}")
  owned=(e.event_category=="EXCHANGE_HOLIDAY" and policy.holiday_event_owned_by_session_validation) or (e.event_category=="SPECIAL_SESSION" and policy.special_session_owned_by_session_validation)
  context_only=(e.event_category in {"WEEKLY_EXPIRY","MONTHLY_EXPIRY"} and policy.expiry_event_is_context_only) or (e.event_category=="ROLLOVER" and policy.rollover_event_is_context_only)
  qualifies=e.event_category in policy.blocking_event_categories and _R[e.severity]>=_R[policy.minimum_blocking_severity] and (e.confirmation_state=="CONFIRMED" or (e.confirmation_state=="TENTATIVE" and e.severity=="EXTREME" and policy.block_on_tentative_extreme_events))
  if qualifies and not owned and not context_only:blocking.append(e.scheduled_market_event_id)
  if e.event_category in policy.warning_event_categories and _R[e.severity]>=_R[policy.minimum_warning_severity] or (e.confirmation_state=="TENTATIVE" and policy.warn_on_tentative_events) or owned or context_only:warn+=1;w.extend(e.warnings or (f"EVENT CONTEXT WARNING FOR {e.scheduled_market_event_id}",))
 if not ev:
  if policy.warn_on_missing_event_calendar:w.append("EVENT CALENDAR IS UNAVAILABLE")
  status="UNAVAILABLE";risk="UNAVAILABLE";entry="UNAVAILABLE"
 elif b or blocking:status="BLOCKED";risk=high if high!="UNAVAILABLE" else "UNAVAILABLE";entry="BLOCKED";b.extend(f"EVENT POLICY BLOCKS {x}" for x in blocking)
 else:
  risk="NONE" if high=="UNAVAILABLE" else high;session=any(e.event_category in {"EXCHANGE_HOLIDAY","SPECIAL_SESSION"} for e in ev if e.scheduled_market_event_id in active+upcoming+cool)
  entry="SESSION_OWNED" if session else "WARNING" if w else "OPEN";status="READY_WITH_WARNINGS" if w else "READY"
 return EventRiskContextResultV1(result_id,created_at,i[0],i[1],ev,status,risk,entry,True if not blocking else policy.allow_analysis_during_entry_block,False if blocking else True,len(active),len(upcoming),len(cool),len(blocking),warn,high,tuple(sorted(active)),tuple(sorted(upcoming)),tuple(sorted(cool)),tuple(sorted(blocking)),_m(support),(),_m(b),_m(w),{e.scheduled_market_event_id:e.source_timestamp for e in ev})
