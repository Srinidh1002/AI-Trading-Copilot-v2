"""Provider-free deterministic Task 2D explanation projection."""
from services.contracts.market_decision_explanation_v1 import MarketEvidenceExplanationEntryV1,MarketDecisionExplanationV1
from services.contracts.market_decision_explanation_policy_v1 import MarketDecisionExplanationPolicyV1
def build_market_decision_explanation(*,candidate,action,cycle_id,observation_id,evaluated_at,contributions=None,ledger=None,terminal_codes=(),policy=MarketDecisionExplanationPolicyV1()):
 if type(policy) is not MarketDecisionExplanationPolicyV1:raise TypeError("policy")
 symbol,exchange=action.underlying_symbol,action.exchange
 if candidate is not None and (candidate.underlying_symbol,candidate.exchange)!=(symbol,exchange):raise ValueError("candidate identity")
 entries=[]
 def add(category,component,reason,direction="UNAVAILABLE",status="READY",source_id=None,timestamp=None,numeric=None,counted=False):entries.append(MarketEvidenceExplanationEntryV1(f"{cycle_id}:{component}:{reason}",category,component,source_id,None,direction,status,{"BLOCKER":1,"CONTRADICTION":2,"SUITABILITY":3,"SUPPORTING":4,"OPPOSING":5,"QUALITY":6,"WARNING":9,"INFORMATIONAL":10}[category],reason,numeric,timestamp,evaluated_at,counted,False))
 for code in dict.fromkeys((*action.blockers,*terminal_codes)):add("BLOCKER","candidate",code,status="BLOCKED")
 if candidate is not None:
  for code in dict.fromkeys(candidate.contradictions):add("CONTRADICTION","candidate",code,direction="CONFLICTING",status="CONFLICTING")
  for code in dict.fromkeys(candidate.warnings):add("WARNING","candidate",code)
  if action.action in {"CALL","PUT"}:add("SUPPORTING","action",action.reasons[0],direction=candidate.direction,numeric=candidate.confidence,counted=True)
  elif action.action=="WAIT":add("OPPOSING","action",action.reasons[0],direction=candidate.direction)
  suitability=getattr(candidate.regime,"entry_suitability",None)
  if suitability=="SUITABLE":add("SUPPORTING","regime","REGIME_SUITABLE",status="READY",source_id=getattr(candidate.regime,"market_regime_result_id",None))
  elif suitability is not None:add("SUITABILITY","regime","REGIME_BLOCKED" if suitability in {"BLOCKED","NOT_SUITABLE"} else "REGIME_CAUTION",status="BLOCKED" if suitability in {"BLOCKED","NOT_SUITABLE"} else "READY")
 if contributions is not None:
  for item in contributions.contributions:
   add("INFORMATIONAL",f"pillar:{item.pillar_name}","GROUPED_PILLAR_EVIDENCE" if item.provenance_classification=="GROUPED" else "PILLAR_UNAVAILABLE",direction=item.direction,status=item.status,source_id=item.source_result_id,timestamp=item.source_timestamp)
 entries=tuple(sorted(entries,key=lambda x:x.explanation_entry_id))
 return MarketDecisionExplanationV1(f"explanation:{cycle_id}:{observation_id}",symbol,exchange,cycle_id,observation_id,getattr(candidate,"candidate_id",None),action.action_id,action.action,action.candidate_eligibility,action.candidate_direction,action.confidence,action.score,action.regime_suitability,entries,action.blockers,action.warnings,action.reasons,tuple(dict.fromkeys(terminal_codes)))
