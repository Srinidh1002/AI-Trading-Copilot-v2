"""Pure candidate eligibility normalization; no ranking or scoring."""
from __future__ import annotations
import json
from dataclasses import dataclass
from services.contracts.market_opportunity_candidate_v1 import MarketOpportunityCandidateV1
from services.contracts.four_market_ranking_policy_v1 import FourMarketRankingPolicyV1,DEFAULT_FOUR_MARKET_RANKING_POLICY
@dataclass(frozen=True,slots=True)
class CandidateEligibilityEvaluationV1:
 underlying_symbol:str;exchange:str;eligibility_state:str;rankable:bool;blockers:tuple[str,...]=();contradictions:tuple[str,...]=();warnings:tuple[str,...]=();failed_thresholds:tuple[str,...]=();freshness_failure:str="NONE";missing_required_reference:bool=False;missing_optional_references:tuple[str,...]=();liquidity_failure:bool=False;execution_quality_failure:bool=False;spread_limit_breach:bool=False;slippage_limit_breach:bool=False;analysis_allowed:bool=True;new_entries_allowed:bool=True
 def to_dict(self):return {n:list(getattr(self,n)) if isinstance(getattr(self,n),tuple) else getattr(self,n) for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"))
 def semantic_dict(self):return self.to_dict()
def _tuple(values):return tuple(dict.fromkeys(x for x in values if x))
def evaluate_candidate_eligibility(candidate:MarketOpportunityCandidateV1,policy:FourMarketRankingPolicyV1=DEFAULT_FOUR_MARKET_RANKING_POLICY)->CandidateEligibilityEvaluationV1:
 if type(candidate) is not MarketOpportunityCandidateV1:raise TypeError("candidate")
 if type(policy) is not FourMarketRankingPolicyV1:raise TypeError("policy")
 b=list(candidate.blockers);c=list(candidate.contradictions);w=list(candidate.warnings);failed=[];missing=[]
 for name,value,limit in (("OPPORTUNITY_CONFIDENCE",candidate.opportunity_confidence,policy.minimum_opportunity_confidence),("REGIME_SUITABILITY",candidate.regime_suitability_score,policy.minimum_regime_suitability_score),("DATA_QUALITY",candidate.data_quality_score,policy.minimum_data_quality_score)):
  if value<limit:failed.append(name)
 for avail,name in ((candidate.trade_opportunity_available,"TRADE_OPPORTUNITY"),(candidate.option_chain_available,"OPTION_CHAIN"),(candidate.broader_market_available,"BROADER_MARKET"),(candidate.external_context_available,"EXTERNAL_CONTEXT"),(candidate.liquidity_available,"LIQUIDITY"),(candidate.execution_quality_available,"EXECUTION_QUALITY")):
  if not avail:missing.append(name)
 if candidate.liquidity_available and candidate.liquidity_score<policy.minimum_liquidity_score:failed.append("LIQUIDITY")
 if candidate.execution_quality_available and candidate.execution_quality_score<policy.minimum_execution_quality_score:failed.append("EXECUTION_QUALITY")
 liquidity="LIQUIDITY" in failed;execution="EXECUTION_QUALITY" in failed
 if candidate.candidate_status=="BLOCKED" or (not candidate.analysis_allowed and policy.block_candidate_when_analysis_disallowed) or (not candidate.new_entries_allowed and policy.block_candidate_when_new_entries_disallowed) or candidate.entry_restriction_state=="BLOCKED" or (candidate.market_regime.primary_regime=="BLOCKED" and policy.block_candidate_on_blocked_regime) or (liquidity and policy.block_on_liquidity_failure) or (execution and policy.block_on_execution_quality_failure):state="BLOCKED";b.append("CANDIDATE_BLOCKED")
 elif candidate.candidate_status=="UNAVAILABLE" or candidate.market_regime.primary_regime=="UNAVAILABLE" or candidate.data_quality_state=="UNAVAILABLE" or candidate.freshness_state=="UNAVAILABLE" or any(x in failed for x in ("OPPORTUNITY_CONFIDENCE","REGIME_SUITABILITY","DATA_QUALITY")):state="UNAVAILABLE";b.append("CANDIDATE_UNAVAILABLE")
 elif candidate.candidate_status=="CONFLICTING" or candidate.market_regime.primary_regime=="CONFLICTING" or c:state="CONFLICTING"
 else:
  if missing and policy.warn_on_missing_optional_reference:w.extend("MISSING_"+x for x in missing)
  if candidate.entry_restriction_state in {"WARNING","SESSION_OWNED"}:w.append("ENTRY_RESTRICTION_WARNING")
  if liquidity:w.append("LIQUIDITY_THRESHOLD")
  if execution:w.append("EXECUTION_QUALITY_THRESHOLD")
  state="ELIGIBLE_WITH_WARNINGS" if w or candidate.candidate_status=="READY_WITH_WARNINGS" else "ELIGIBLE"
 rankable=state=="ELIGIBLE" or state=="ELIGIBLE_WITH_WARNINGS" and policy.allow_warning_candidate_to_rank or state=="CONFLICTING" and policy.allow_conflicting_candidate_to_rank
 return CandidateEligibilityEvaluationV1(candidate.underlying_symbol,candidate.exchange,state,rankable,_tuple(b),_tuple(c),_tuple(w),tuple(failed),"UNAVAILABLE" if candidate.freshness_state=="UNAVAILABLE" else candidate.freshness_state if candidate.freshness_state in {"STALE","FUTURE","MIXED"} else "NONE",False,tuple(missing),liquidity,execution,False,False,candidate.analysis_allowed,candidate.new_entries_allowed)
