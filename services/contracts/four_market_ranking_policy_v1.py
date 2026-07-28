"""Immutable configuration for future four-market opportunity ranking."""
from __future__ import annotations
import json,math
from dataclasses import dataclass
from types import MappingProxyType
from services.core.market_identity import normalize_market_identity
_ID=("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")
_EL=("BLOCKED","UNAVAILABLE","CONFLICTING","ELIGIBLE_WITH_WARNINGS","ELIGIBLE")
_TIE=("ELIGIBILITY","FINAL_SCORE","OPPORTUNITY_CONFIDENCE","REGIME_SUITABILITY","DATA_QUALITY","LIQUIDITY","EXECUTION_QUALITY","FEWER_WARNINGS","FEWER_CONTRADICTIONS","LOWER_SPREAD","LOWER_SLIPPAGE","CANONICAL_MARKET_ORDER")
_TS=("NO_TIE","TIE_RESOLVED","ALL_INELIGIBLE")
_W=("opportunity_confidence_weight","regime_suitability_weight","technical_confirmation_weight","option_chain_confirmation_weight","broader_market_confirmation_weight","external_context_confirmation_weight","data_quality_weight","liquidity_weight","execution_quality_weight")
_WK=("OPPORTUNITY_CONFIDENCE","REGIME_SUITABILITY","TECHNICAL_CONFIRMATION","OPTION_CHAIN_CONFIRMATION","BROADER_MARKET_CONFIRMATION","EXTERNAL_CONTEXT_CONFIRMATION","DATA_QUALITY","LIQUIDITY","EXECUTION_QUALITY")
def _unit(v,n):
 if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(float(v)) or not 0<=float(v)<=1:raise ValueError(n)
 return float(v)
def _nonneg(v,n):
 if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(float(v)) or float(v)<0:raise ValueError(n)
 return float(v)
@dataclass(frozen=True,slots=True)
class FourMarketRankingPolicyV1:
 required_market_identities:tuple[tuple[str,str],...]=_ID; eligibility_precedence:tuple[str,...]=_EL
 block_candidate_when_analysis_disallowed:bool=True;block_candidate_when_new_entries_disallowed:bool=True;block_candidate_on_blocked_regime:bool=True;mark_unavailable_on_unavailable_regime:bool=True;mark_conflicting_on_conflicting_regime:bool=True;allow_conflicting_candidate_to_rank:bool=False;allow_warning_candidate_to_rank:bool=True;require_all_four_market_slots:bool=True
 minimum_opportunity_confidence:float=.5;minimum_regime_suitability_score:float=.5;minimum_data_quality_score:float=.5;minimum_liquidity_score:float=.4;minimum_execution_quality_score:float=.4
 opportunity_confidence_weight:float=.30;regime_suitability_weight:float=.20;technical_confirmation_weight:float=.15;option_chain_confirmation_weight:float=.15;broader_market_confirmation_weight:float=.05;external_context_confirmation_weight:float=.05;data_quality_weight:float=.05;liquidity_weight:float=.025;execution_quality_weight:float=.025
 warning_penalty:float=.05;conflict_penalty:float=.20;missing_optional_evidence_penalty:float=.05;stale_data_penalty:float=.10;event_risk_penalty:float=.10;spread_penalty:float=.05;slippage_penalty:float=.05
 exclude_unavailable_optional_scores_from_denominator:bool=True;apply_missing_optional_evidence_penalty_once:bool=True;fail_closed_on_missing_required_reference:bool=True;warn_on_missing_optional_reference:bool=True
 maximum_normalized_spread:float=.20;maximum_normalized_slippage:float=.20;block_on_liquidity_failure:bool=True;block_on_execution_quality_failure:bool=True;warn_on_spread_limit_breach:bool=True;warn_on_slippage_limit_breach:bool=True
 tie_breaking_order:tuple[str,...]=_TIE;tie_tolerance:float=1e-12;tie_state_values:tuple[str,...]=_TS
 select_none_when_all_candidates_ineligible:bool=True;preserve_all_candidates_in_result:bool=True;preserve_rejection_reasons:bool=True;rank_only_eligible_candidates:bool=True
 maximum_candidate_age_seconds:float=300.;future_timestamp_tolerance_seconds:float=5.;maximum_candidate_timestamp_skew_seconds:float=900.;execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="1.0"
 def __post_init__(self):
  ids=self.required_market_identities
  if not isinstance(ids,tuple) or len(ids)!=4:raise ValueError("required_market_identities")
  norm=[]
  for i in ids:
   if not isinstance(i,tuple) or len(i)!=2 or type(i[0]) is not str or type(i[1]) is not str or normalize_market_identity(*i) not in _ID:raise ValueError("required_market_identities")
   norm.append(normalize_market_identity(*i))
  if set(norm)!=set(_ID) or len(set(norm))!=4:raise ValueError("required_market_identities")
  object.__setattr__(self,"required_market_identities",_ID)
  if self.eligibility_precedence!=_EL or self.tie_breaking_order!=_TIE or self.tie_state_values!=_TS:raise ValueError("state ordering")
  for n in ("block_candidate_when_analysis_disallowed","block_candidate_when_new_entries_disallowed","block_candidate_on_blocked_regime","mark_unavailable_on_unavailable_regime","mark_conflicting_on_conflicting_regime","allow_conflicting_candidate_to_rank","allow_warning_candidate_to_rank","require_all_four_market_slots","exclude_unavailable_optional_scores_from_denominator","apply_missing_optional_evidence_penalty_once","fail_closed_on_missing_required_reference","warn_on_missing_optional_reference","block_on_liquidity_failure","block_on_execution_quality_failure","warn_on_spread_limit_breach","warn_on_slippage_limit_breach","select_none_when_all_candidates_ineligible","preserve_all_candidates_in_result","preserve_rejection_reasons","rank_only_eligible_candidates"):
   if type(getattr(self,n)) is not bool:raise ValueError(n)
  for n in ("minimum_opportunity_confidence","minimum_regime_suitability_score","minimum_data_quality_score","minimum_liquidity_score","minimum_execution_quality_score","warning_penalty","conflict_penalty","missing_optional_evidence_penalty","stale_data_penalty","event_risk_penalty","spread_penalty","slippage_penalty","maximum_normalized_spread","maximum_normalized_slippage") :object.__setattr__(self,n,_unit(getattr(self,n),n))
  for n in _W:object.__setattr__(self,n,_nonneg(getattr(self,n),n))
  if not any(getattr(self,n) for n in _W):raise ValueError("ranking_weights")
  for n in ("tie_tolerance","future_timestamp_tolerance_seconds","maximum_candidate_timestamp_skew_seconds"):object.__setattr__(self,n,_nonneg(getattr(self,n),n))
  self_age=_nonneg(self.maximum_candidate_age_seconds,"maximum_candidate_age_seconds")
  if self_age<=0:raise ValueError("maximum_candidate_age_seconds")
  object.__setattr__(self,"maximum_candidate_age_seconds",self_age)
  if self.execution_mode!="PAPER" or self.live_execution_eligible is not False or type(self.schema_version) is not str or not self.schema_version.strip():raise ValueError("execution")
 @property
 def ranking_weights(self):return MappingProxyType(dict(zip(_WK,(getattr(self,n) for n in _W))))
 def to_dict(self):
  d={n:getattr(self,n) for n in self.__dataclass_fields__};d["ranking_weights"]=dict(self.ranking_weights);return d
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"))
 def semantic_dict(self):return self.to_dict()
DEFAULT_FOUR_MARKET_RANKING_POLICY=FourMarketRankingPolicyV1()
