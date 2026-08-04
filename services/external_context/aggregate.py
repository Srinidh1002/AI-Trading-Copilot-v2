from __future__ import annotations
from datetime import datetime
from services.contracts.external_context_policy_v1 import DEFAULT_EXTERNAL_CONTEXT_POLICY,ExternalContextPolicyV1
from services.contracts.global_market_context_result_v1 import GlobalMarketContextResultV1
from services.contracts.institutional_flow_context_result_v1 import InstitutionalFlowContextResultV1
from services.contracts.event_risk_context_result_v1 import EventRiskContextResultV1
from services.contracts.external_market_context_result_v1 import ExternalMarketContextResultV1
from services.core.market_identity import normalize_market_identity
def evaluate_external_market_context(*,underlying_symbol:str,exchange:str,global_context:GlobalMarketContextResultV1|None,institutional_context:InstitutionalFlowContextResultV1|None,event_context:EventRiskContextResultV1|None,policy:ExternalContextPolicyV1=DEFAULT_EXTERNAL_CONTEXT_POLICY,created_at:datetime,result_id:str)->ExternalMarketContextResultV1:
 i=normalize_market_identity(underlying_symbol,exchange)
 if i is None:raise ValueError("identity")
 if not isinstance(policy,ExternalContextPolicyV1):raise TypeError("policy")
 if not isinstance(created_at,datetime) or created_at.tzinfo is None:raise ValueError("time")
 if not isinstance(result_id,str) or not result_id.strip():raise ValueError("id")
 comps=(global_context,institutional_context,event_context)
 for c,t in zip(comps,(GlobalMarketContextResultV1,InstitutionalFlowContextResultV1,EventRiskContextResultV1)):
  if c is not None and (not isinstance(c,t) or (c.underlying_symbol,c.exchange)!=i):raise ValueError("component")
 w=[];b=[];x=[];support=[];available=sum(c is not None and c.context_status not in {"UNAVAILABLE","BLOCKED"} for c in comps);unavailable=3-available
 for c,name,req in zip(comps,("GLOBAL","INSTITUTIONAL","EVENT"),(policy.require_global_context,policy.require_institutional_context,policy.require_event_context)):
  if c is None or c.context_status=="UNAVAILABLE":
   w.append(f"{name} CONTEXT IS UNAVAILABLE")
   if req and policy.fail_closed_on_invalid_mandatory_component:b.append(f"REQUIRED {name} CONTEXT IS UNAVAILABLE")
  elif c.context_status=="BLOCKED":b.extend(c.blockers or (f"{name} CONTEXT IS BLOCKED",))
  else:w.extend(c.warnings);b.extend(c.blockers)
 if available<policy.minimum_available_component_count:b.append("MINIMUM COMPONENT AVAILABILITY NOT MET")
 dirs=[]
 for c,weight,name in ((global_context,policy.global_context_weight,"GLOBAL"),(institutional_context,policy.institutional_context_weight,"INSTITUTIONAL")):
  if c and c.context_status not in {"UNAVAILABLE","BLOCKED"}:
   if c.aggregate_direction in {"POSITIVE","NEGATIVE"}:dirs.append((c.aggregate_direction,c.aggregate_strength,weight,name))
   elif c.aggregate_direction=="CONFLICTING":x.append(f"{name} CONTEXT IS CONFLICTING")
 if len({d[0] for d in dirs})>1:x.append("GLOBAL AND INSTITUTIONAL CONTEXT CONFLICT")
 if event_context:
  risk,entry=event_context.event_risk_level,event_context.entry_restriction_state;analysis,evententries=event_context.analysis_allowed,event_context.new_entries_allowed
  if event_context.context_status=="BLOCKED" and policy.event_block_precedence:b.extend(event_context.blockers or ("EVENT CONTEXT IS BLOCKED",))
 else:risk,entry,analysis,evententries="UNAVAILABLE","UNAVAILABLE",True,True
 if b:status,direction,strength,conf="BLOCKED","UNAVAILABLE",0,"UNAVAILABLE"
 elif x:status,direction,strength,conf="CONFLICTING","CONFLICTING",0,"CONFLICTING"
 elif available == 0:
    status, direction, strength, conf = (
        "UNAVAILABLE",
        "UNAVAILABLE",
        0,
        "UNAVAILABLE",
    )
 else:
  direction=dirs[0][0] if dirs else "UNAVAILABLE";strength=sum(d[1]*d[2] for d in dirs)/sum(d[2] for d in dirs) if dirs else 0;conf="CONFIRMING" if len(dirs)==2 else "PARTIAL" if dirs else "UNAVAILABLE";status="READY_WITH_WARNINGS" if w or conf=="PARTIAL" or entry in {"WARNING","SESSION_OWNED"} else "READY"
 stamps={}
 for c,n in ((global_context,"GLOBAL"),(institutional_context,"INSTITUTIONAL"),(event_context,"EVENT")):
  if c:stamps.update({f"{n}_{k}":v for k,v in c.source_timestamps.items()})
 return ExternalMarketContextResultV1(result_id,created_at,i[0],i[1],global_context,institutional_context,event_context,status,direction,strength,conf,risk,entry,analysis and not bool(b),evententries and not bool(b),available,unavailable,sum(d[0]==direction for d in dirs),len(x),tuple(sorted(set(support))),tuple(sorted(set(x))),tuple(sorted(set(b))),tuple(sorted(set(w))),stamps)
