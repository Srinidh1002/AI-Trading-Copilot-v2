"""Pure Task 2C action projection; no planning or execution imports."""
from services.contracts.pre_entry_action_policy_v1 import PreEntryActionPolicyV1
from services.contracts.pre_entry_market_action_v1 import PreEntryMarketActionV1

def resolve_pre_entry_market_action(*,candidate,cycle_id:str,observation_id:str,evaluated_at,ledger=None,policy=PreEntryActionPolicyV1(),failure_codes:tuple[str,...]=()):
 if type(policy) is not PreEntryActionPolicyV1:raise TypeError("policy")
 if candidate is None:
  return PreEntryMarketActionV1(f"action:{cycle_id}:{observation_id}","NIFTY","NSE",cycle_id,observation_id,None,"UNAVAILABLE","UNAVAILABLE","UNAVAILABLE",0.,0.,None,False,getattr(ledger,"ledger_id",None),evaluated_at,blockers=tuple(failure_codes) or ("CANDIDATE_UNAVAILABLE",),reasons=("CANDIDATE_COMPOSITION_FAILED",))
 symbol,exchange=candidate.underlying_symbol,candidate.exchange; suitability=getattr(candidate.regime,"entry_suitability",None); ledger_id=getattr(ledger,"ledger_id",None)
 unavailable=bool(candidate.blockers or candidate.contradictions or candidate.direction in {"UNAVAILABLE","CONFLICTING"} or candidate.eligibility in {"UNAVAILABLE","CONFLICTING"} or suitability in {"BLOCKED","NOT_SUITABLE","UNAVAILABLE"})
 if unavailable:
  code="EVIDENCE_CONFLICTING" if candidate.contradictions else "REGIME_BLOCKED" if suitability in {"BLOCKED","NOT_SUITABLE","UNAVAILABLE"} else "REQUIRED_EVIDENCE_UNAVAILABLE"
  return PreEntryMarketActionV1(f"action:{cycle_id}:{observation_id}",symbol,exchange,cycle_id,observation_id,candidate.candidate_id,"UNAVAILABLE","UNAVAILABLE",candidate.eligibility,0.,0.,suitability,False,ledger_id,evaluated_at,blockers=tuple(dict.fromkeys((*candidate.blockers,*candidate.contradictions,code))),reasons=(code,),warnings=candidate.warnings)
 if candidate.eligibility=="ELIGIBLE" and candidate.direction=="BULLISH": action,reason="CALL","ELIGIBLE_BULLISH_CANDIDATE"
 elif candidate.eligibility=="ELIGIBLE" and candidate.direction=="BEARISH": action,reason="PUT","ELIGIBLE_BEARISH_CANDIDATE"
 else: action,reason="WAIT","DIRECTION_NEUTRAL_NO_ENTRY" if candidate.direction=="NEUTRAL" else "VALID_EVIDENCE_INSUFFICIENT_CONFIRMATION"
 return PreEntryMarketActionV1(f"action:{cycle_id}:{observation_id}",symbol,exchange,cycle_id,observation_id,candidate.candidate_id,action,candidate.direction,candidate.eligibility,candidate.confidence,candidate.score,suitability,action in {"CALL","PUT"},ledger_id,evaluated_at,reasons=(reason,),warnings=candidate.warnings)
