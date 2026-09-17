"""Pure deterministic aggregation of supplied external market observations."""
from __future__ import annotations
from datetime import datetime
from services.contracts.external_context_policy_v1 import DEFAULT_EXTERNAL_CONTEXT_POLICY, ExternalContextPolicyV1
from services.contracts.external_market_observation_v1 import ExternalMarketObservationV1
from services.contracts.global_market_context_result_v1 import GlobalMarketContextResultV1
from services.core.market_identity import normalize_market_identity
_GROUPS=(("US EQUITY",("SP500","NASDAQ","DOW_JONES")),("CRUDE",("BRENT_CRUDE","WTI_CRUDE")),("ASIA",("NIKKEI_225","HANG_SENG","SHANGHAI_COMPOSITE")))
def _msg(items):return tuple(sorted({" ".join(x.upper().split()) for x in items if x}))
def evaluate_global_market_context(*,underlying_symbol:str,exchange:str,observations:tuple[ExternalMarketObservationV1,...],policy:ExternalContextPolicyV1=DEFAULT_EXTERNAL_CONTEXT_POLICY,created_at:datetime,result_id:str)->GlobalMarketContextResultV1:
 identity=normalize_market_identity(underlying_symbol,exchange)
 if identity is None:raise ValueError("unsupported market identity")
 if not isinstance(observations,tuple):raise TypeError("observations must be a tuple")
 if not isinstance(policy,ExternalContextPolicyV1):raise TypeError("policy must be ExternalContextPolicyV1")
 if not isinstance(created_at,datetime) or created_at.tzinfo is None or created_at.utcoffset() is None:raise ValueError("created_at must be timezone-aware")
 if not isinstance(result_id,str) or not result_id.strip():raise ValueError("result_id must not be empty")
 seen=set()
 for o in observations:
  if not isinstance(o,ExternalMarketObservationV1):raise TypeError("observations must contain ExternalMarketObservationV1")
  if o.canonical_name in seen:raise ValueError("duplicate canonical observation name")
  if o.affected_market_identities and identity not in o.affected_market_identities:raise ValueError("observation does not apply to target identity")
  seen.add(o.canonical_name)
 obs=tuple(sorted(observations,key=lambda x:x.canonical_name));required=set(policy.required_observation_names.get(identity,()));optional=set(policy.optional_observation_names.get(identity,()));present={x.canonical_name for x in obs};warnings=[];blockers=[];contradictions=[];support=[];available=[];contrib=[];delayed=0
 for missing in sorted(required-present):
  (blockers if policy.block_on_missing_required_observation else warnings).append(f"REQUIRED {missing} OBSERVATION IS MISSING")
 for missing in sorted(optional-present):
  if policy.warn_on_missing_optional_observation:warnings.append(f"OPTIONAL {missing} OBSERVATION IS MISSING")
 for o in obs:
  is_required=o.canonical_name in required;age=(created_at-o.source_timestamp).total_seconds();usable=o.observation_status in {"READY","READY_WITH_WARNINGS"};reason=None
  if age < -policy.future_timestamp_tolerance_seconds:reason="FUTURE"
  elif age > policy.maximum_observation_age_seconds.get(o.canonical_name,0):reason="STALE"
  elif o.observation_status in {"STALE","UNAVAILABLE","BLOCKED"}:reason=o.observation_status
  elif o.observation_status=="DELAYED":
   delayed+=1
   if not (not is_required and policy.allow_delayed_optional_observations and o.delay_seconds<=policy.maximum_acceptable_delay_seconds):reason="DELAYED"
   else:usable=True;warnings.append(f"DELAYED {o.canonical_name} OBSERVATION WAS DOWNWEIGHTED")
  if reason:
   if is_required and ((reason=="FUTURE" and policy.block_on_future_required_observation) or (reason=="STALE" and policy.block_on_stale_required_observation) or (reason=="DELAYED" and policy.block_on_delayed_required_observation) or reason in {"UNAVAILABLE","BLOCKED"}):blockers.append(f"REQUIRED {o.canonical_name} OBSERVATION IS {reason}")
   elif is_required:warnings.append(f"REQUIRED {o.canonical_name} OBSERVATION IS {reason}")
   elif (reason=="STALE" and policy.warn_on_stale_optional_observation) or reason!="STALE":warnings.append(f"OPTIONAL {o.canonical_name} OBSERVATION IS {reason}")
   continue
  if o.observation_status=="READY_WITH_WARNINGS":warnings.extend(o.warnings)
  available.append(o);factor=0.0
  if o.change_percent is None:warnings.append(f"{o.canonical_name} CHANGE PERCENT IS UNAVAILABLE")
  else:
   magnitude=abs(o.change_percent)
   if magnitude>policy.flat_change_tolerance_percent:
    factor=1.0 if magnitude>=policy.strong_directional_change_percent else max(0.0,(magnitude-policy.minimum_directional_change_percent)/(policy.strong_directional_change_percent-policy.minimum_directional_change_percent))
  weight=policy.observation_weights.get(o.canonical_name,0.0)*factor
  if o.observation_status=="DELAYED":weight*=1-policy.delayed_observation_penalty
  if o.direction in {"POSITIVE","NEGATIVE","FLAT"}:contrib.append([o.canonical_name,o.direction,weight])
  if weight and o.direction in {"POSITIVE","NEGATIVE"}:support.append(f"{o.canonical_name} SUPPORTS {o.direction} GLOBAL CONTEXT")
 # Cap each correlated group at its largest configured member weight, preserving mixed support.
 for label,members in _GROUPS:
  group=[x for x in contrib if x[0] in members];total=sum(x[2] for x in group);cap=max((policy.observation_weights.get(x,0.0) for x in members),default=0.0)
  if total>cap>0:
   for x in group:x[2]*=cap/total
  if {x[1] for x in group if x[2]}>={"POSITIVE","NEGATIVE"}:contradictions.append(f"{label} GROUP IS MIXED")
 pos=sum(x[2] for x in contrib if x[1]=="POSITIVE");neg=sum(x[2] for x in contrib if x[1]=="NEGATIVE");flat=sum(x[2] for x in contrib if x[1]=="FLAT")
 if pos and neg and min(pos,neg)>0:contradictions.append("GLOBAL OBSERVATIONS ARE CONFLICTING")
 if len(available)<policy.minimum_available_global_observations: blockers.append("MINIMUM GLOBAL OBSERVATION AVAILABILITY NOT MET")
 unavailable=len(obs)-len(available)
 if blockers:status,direction,strength,confirmation="BLOCKED","UNAVAILABLE",0.0,"UNAVAILABLE"
 elif contradictions:status,direction,strength,confirmation="CONFLICTING","CONFLICTING",0.0,"CONFLICTING"
 elif not pos and not neg:
  if available:status,direction,strength,confirmation=("READY_WITH_WARNINGS" if warnings else "READY"),"FLAT",0.0,"NOT_CONFIRMING"
  else:status,direction,strength,confirmation="UNAVAILABLE","UNAVAILABLE",0.0,"UNAVAILABLE"
 else:
  direction="POSITIVE" if pos>neg else "NEGATIVE";denom=pos+neg+flat;strength=max(0.0,min(1.0,max(pos,neg)/denom-sum((policy.delayed_observation_penalty if o.observation_status=="DELAYED" else 0.0) for o in available)-policy.missing_optional_observation_penalty*len(optional-present)))
  confirmation="CONFIRMING" if strength>=policy.global_alignment_strength_threshold and len(available)>=policy.minimum_global_confirmation_count else "PARTIAL"
  status="READY" if not warnings and confirmation=="CONFIRMING" else "READY_WITH_WARNINGS"
 return GlobalMarketContextResultV1(result_id,created_at,identity[0],identity[1],obs,status,direction,strength,confirmation,len(available),unavailable,delayed,pos,neg,flat,_msg(support),_msg(contradictions),_msg(blockers),_msg(warnings),{o.canonical_name:o.source_timestamp for o in obs})
