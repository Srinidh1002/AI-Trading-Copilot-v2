"""Pure contextual evaluation of supplied institutional-flow snapshots."""
from __future__ import annotations
from datetime import datetime
from services.contracts.external_context_policy_v1 import DEFAULT_EXTERNAL_CONTEXT_POLICY,ExternalContextPolicyV1
from services.contracts.institutional_flow_snapshot_v1 import InstitutionalFlowSnapshotV1
from services.contracts.institutional_flow_context_result_v1 import InstitutionalFlowContextResultV1
from services.core.market_identity import normalize_market_identity
def _m(x):return tuple(sorted({" ".join(v.upper().split()) for v in x if v}))
def evaluate_institutional_flow_context(*,underlying_symbol:str,exchange:str,snapshot:InstitutionalFlowSnapshotV1|None,policy:ExternalContextPolicyV1=DEFAULT_EXTERNAL_CONTEXT_POLICY,created_at:datetime,result_id:str)->InstitutionalFlowContextResultV1:
 identity=normalize_market_identity(underlying_symbol,exchange)
 if identity is None:raise ValueError("unsupported market identity")
 if snapshot is not None and not isinstance(snapshot,InstitutionalFlowSnapshotV1):raise TypeError("snapshot must be InstitutionalFlowSnapshotV1 or None")
 if not isinstance(policy,ExternalContextPolicyV1):raise TypeError("policy must be ExternalContextPolicyV1")
 if not isinstance(created_at,datetime) or created_at.tzinfo is None or created_at.utcoffset() is None:raise ValueError("created_at must be timezone-aware")
 if not isinstance(result_id,str) or not result_id.strip():raise ValueError("result_id must not be empty")
 if snapshot and snapshot.affected_market_identities and identity not in snapshot.affected_market_identities:raise ValueError("snapshot does not apply to target identity")
 base=dict(institutional_flow_context_result_id=result_id,created_at=created_at,underlying_symbol=identity[0],exchange=identity[1],snapshot=snapshot,publication_state=snapshot.publication_state if snapshot else "UNAVAILABLE",session_reference=snapshot.session_reference if snapshot else "UNAVAILABLE",source_timestamps={snapshot.source_id:snapshot.source_timestamp} if snapshot else {})
 if snapshot is None:
  w=("INSTITUTIONAL FLOW SNAPSHOT IS MISSING",) if policy.warn_on_missing_institutional_flow else ();b=("REQUIRED INSTITUTIONAL FLOW SNAPSHOT IS MISSING",) if policy.require_institutional_flow else ()
  return InstitutionalFlowContextResultV1(**base,context_status="BLOCKED" if b else "UNAVAILABLE",aggregate_direction="UNAVAILABLE",aggregate_strength=0,confirmation_state="UNAVAILABLE",available_component_count=0,unavailable_component_count=4,cash_direction="UNAVAILABLE",derivatives_direction="UNAVAILABLE",fii_cash_direction="UNAVAILABLE",dii_cash_direction="UNAVAILABLE",fii_index_futures_direction="UNAVAILABLE",fii_index_options_direction="UNAVAILABLE",blockers=b,warnings=w)
 w=list(snapshot.warnings);b=list(snapshot.blockers);c=[];support=[];age=(created_at-snapshot.source_timestamp).total_seconds()
 if age>policy.maximum_institutional_flow_age_seconds or snapshot.flow_status in {"STALE","UNAVAILABLE"}:w.append("INSTITUTIONAL FLOW SNAPSHOT IS STALE OR UNAVAILABLE");
 if (age>policy.maximum_institutional_flow_age_seconds and policy.require_institutional_flow and policy.block_on_stale_institutional_flow) or snapshot.flow_status=="BLOCKED":b.append("INSTITUTIONAL FLOW SNAPSHOT IS BLOCKED OR STALE")
 usable=not b and snapshot.flow_status not in {"STALE","UNAVAILABLE","BLOCKED"}
 if snapshot.publication_state=="PROVISIONAL":
  if not policy.allow_provisional_institutional_flow:usable=False;b.append("PROVISIONAL INSTITUTIONAL FLOW IS DISALLOWED")
  elif policy.warn_on_provisional_institutional_flow:w.append("PROVISIONAL INSTITUTIONAL FLOW WAS DOWNWEIGHTED")
 if snapshot.session_reference=="PREVIOUS_SESSION":
  if not policy.previous_session_flow_allowed:usable=False;b.append("PREVIOUS-SESSION INSTITUTIONAL FLOW IS DISALLOWED")
  else:w.append("PREVIOUS-SESSION FLOW PROVIDES PARTIAL CONTEXT")
 fields=(("fii_cash_direction",snapshot.fii_cash_net,"FII CASH FLOW",snapshot.cash_flow_unit,policy.minimum_meaningful_cash_flow_crore),("dii_cash_direction",snapshot.dii_cash_net,"DII CASH FLOW",snapshot.cash_flow_unit,policy.minimum_meaningful_cash_flow_crore),("fii_index_futures_direction",snapshot.fii_index_futures_net,"INDEX FUTURES POSITIONING",snapshot.derivatives_position_unit,policy.minimum_meaningful_derivatives_notional_crore if snapshot.derivatives_position_unit=="NOTIONAL_CRORE_INR" else policy.minimum_meaningful_contract_count),("fii_index_options_direction",snapshot.fii_index_options_net,"INDEX OPTIONS POSITIONING",snapshot.derivatives_position_unit,policy.minimum_meaningful_derivatives_notional_crore if snapshot.derivatives_position_unit=="NOTIONAL_CRORE_INR" else policy.minimum_meaningful_contract_count))
 dirs=[];strengths=[]
 for key,value,label,unit,threshold in fields:
  if not usable or value is None:direction="UNAVAILABLE";strength=0
  elif value==0:direction="FLAT";strength=0
  elif unit in {"RUPEES","MIXED_NORMALIZED"}:direction="POSITIVE" if value>0 else "NEGATIVE";strength=.5;w.append(f"{label} USES SIGN-ONLY UNIT SEMANTICS")
  elif abs(value)<threshold:direction="FLAT";strength=0
  else:direction="POSITIVE" if value>0 else "NEGATIVE";strength=min(1.,abs(value)/(2*threshold))
  dirs.append(direction);strengths.append(strength)
  if direction in {"POSITIVE","NEGATIVE"}:support.append(f"{label} IS {direction}")
 def combine(a,b,label):
  available=[x for x in (a,b) if x!="UNAVAILABLE"]
  if not available:return "UNAVAILABLE"
  if a in {"POSITIVE","NEGATIVE"} and b in {"POSITIVE","NEGATIVE"} and a!=b:c.append(f"{label} CONFLICT");return "UNAVAILABLE"
  if a==b:return a
  return next((x for x in (a,b) if x not in {"UNAVAILABLE","FLAT"}),"FLAT")
 cash=combine(dirs[0],dirs[1],"FII AND DII CASH FLOWS");deriv=combine(dirs[2],dirs[3],"INDEX FUTURES AND OPTIONS POSITIONING")
 if cash in {"POSITIVE","NEGATIVE"} and deriv in {"POSITIVE","NEGATIVE"} and cash!=deriv:c.append("CASH AND DERIVATIVES CONTEXT CONFLICT")
 if b:status,agg,strength,conf="BLOCKED","UNAVAILABLE",0,"UNAVAILABLE"
 elif c:status,agg,strength,conf="CONFLICTING","CONFLICTING",0,"CONFLICTING"
 else:
  usable_dirs=[x for x in (cash,deriv) if x!="UNAVAILABLE"];agg=next((x for x in usable_dirs if x in {"POSITIVE","NEGATIVE"}),"FLAT" if usable_dirs else "UNAVAILABLE");strength=sum(strengths)/len([x for x in strengths if x is not None]) if usable_dirs else 0
  if snapshot.publication_state=="PROVISIONAL":strength*=1-policy.provisional_flow_penalty
  conf="CONFIRMING" if len(usable_dirs)==2 and agg in {"POSITIVE","NEGATIVE"} else "PARTIAL" if agg in {"POSITIVE","NEGATIVE"} else "NOT_CONFIRMING" if usable_dirs else "UNAVAILABLE";status="UNAVAILABLE" if not usable_dirs else "READY_WITH_WARNINGS" if w or conf=="PARTIAL" else "READY"
 return InstitutionalFlowContextResultV1(**base,context_status=status,aggregate_direction=agg,aggregate_strength=max(0,min(1,strength)),confirmation_state=conf,available_component_count=sum(x!="UNAVAILABLE" for x in dirs),unavailable_component_count=sum(x=="UNAVAILABLE" for x in dirs),cash_direction=cash,derivatives_direction=deriv,fii_cash_direction=dirs[0],dii_cash_direction=dirs[1],fii_index_futures_direction=dirs[2],fii_index_options_direction=dirs[3],supporting_evidence=_m(support),contradictions=_m(c),blockers=_m(b),warnings=_m(w))
