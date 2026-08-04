"""Pure typed parent explanation validated against the existing ranker output."""
from services.contracts.market_decision_explanation_v1 import TwoMarketDecisionExplanationV1,MarketDecisionExplanationV1
from services.contracts.pre_entry_market_action_v1 import PreEntryMarketActionV1

def build_two_market_decision_explanation(*,parent_decision,nifty_action,sensex_action,nifty_explanation,sensex_explanation,parent_action_projection):
 if any((type(nifty_action) is not PreEntryMarketActionV1,type(sensex_action) is not PreEntryMarketActionV1,type(nifty_explanation) is not MarketDecisionExplanationV1,type(sensex_explanation) is not MarketDecisionExplanationV1)):raise TypeError("typed child inputs")
 if (nifty_action.underlying_symbol,nifty_action.exchange)!=("NIFTY","NSE") or (sensex_action.underlying_symbol,sensex_action.exchange)!=("SENSEX","BSE"):raise ValueError("child identity")
 cycle=parent_decision.parent_cycle_id
 if nifty_action.cycle_id!=cycle or sensex_action.cycle_id!=cycle or nifty_explanation.cycle_id!=cycle or sensex_explanation.cycle_id!=cycle:
  return TwoMarketDecisionExplanationV1(f"parent-explanation:{cycle}",cycle,parent_decision.decision_result_id,"UNAVAILABLE","UNAVAILABLE","NONE",None,None,None,None,(),(),(),(),("PARENT_EXPLANATION_INVARIANT_VIOLATION",),nifty_explanation.explanation_id,sensex_explanation.explanation_id,"FAILED",("PARENT_EXPLANATION_INVARIANT_VIOLATION",),(),parent_decision.completed_at)
 selected=parent_decision.selected_market
 projection_action=parent_action_projection["parent_action"]
 entries={entry.child.underlying_symbol:entry for entry in parent_decision.entries}
 if selected is None:
  return TwoMarketDecisionExplanationV1(f"parent-explanation:{cycle}",cycle,parent_decision.decision_result_id,parent_decision.decision,projection_action,"NONE",None,None,None,None,(),(),(),(),tuple(parent_decision.blockers or ("NO_ACTIONABLE_MARKET",)),nifty_explanation.explanation_id,sensex_explanation.explanation_id,"VALID",tuple(parent_decision.blockers),(),parent_decision.completed_at)
 symbol,exchange=selected; action=nifty_action if symbol=="NIFTY" else sensex_action; other=sensex_action if symbol=="NIFTY" else nifty_action
 if action.action not in {"CALL","PUT"} or projection_action!=action.action or parent_decision.selected_candidate_id!=action.candidate_id:
  return TwoMarketDecisionExplanationV1(f"parent-explanation:{cycle}",cycle,parent_decision.decision_result_id,"UNAVAILABLE","UNAVAILABLE","NONE",None,None,None,None,(),(),(),(),("PARENT_EXPLANATION_INVARIANT_VIOLATION",),nifty_explanation.explanation_id,sensex_explanation.explanation_id,"FAILED",("PARENT_EXPLANATION_INVARIANT_VIOLATION",),(),parent_decision.completed_at)
 loser=entries[other.underlying_symbol]
 reason=loser.outcome_reason; rationale=tuple(loser.rationale)
 tie=(reason,) + rationale if reason=="TIE_BREAK_LOSS" else ()
 return TwoMarketDecisionExplanationV1(f"parent-explanation:{cycle}",cycle,parent_decision.decision_result_id,parent_decision.decision,action.action,symbol,action.action,action.candidate_id,symbol,other.underlying_symbol,(f"SELECTED_{symbol}_{action.action}",),(reason,),rationale,tie,(),nifty_explanation.explanation_id,sensex_explanation.explanation_id,"VALID",(),(),parent_decision.completed_at)
