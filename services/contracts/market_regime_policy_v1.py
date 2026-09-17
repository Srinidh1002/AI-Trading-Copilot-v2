"""Immutable interpretation policy for future canonical market regimes."""
from __future__ import annotations
import json,math
from dataclasses import dataclass,field
from types import MappingProxyType
from typing import Any,Mapping
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES,normalize_market_identity
_COMP={"TECHNICAL","BROADER_MARKET","EXTERNAL_CONTEXT","MARKET_SESSION"};_ENTRY={"SUITABLE","SUITABLE_WITH_WARNINGS","NOT_SUITABLE","BLOCKED","UNAVAILABLE"};_EVENT=("NONE","LOW","MODERATE","HIGH","EXTREME","UNAVAILABLE");_PRECEDENCE=("BLOCKED","EVENT_RISK","CONFLICTING","HIGH_VOLATILITY","UNAVAILABLE","DIRECTIONAL")
def _unit(v,n):
 if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(float(v)) or not 0<=float(v)<=1:raise ValueError(n)
 return float(v)
def _aggregate_weight(v,n):
 if isinstance(v,bool) or not isinstance(v,(int,float)):raise ValueError(n)
 v=float(v)
 if not math.isfinite(v) or v<0:raise ValueError(n)
 return v
def _maps(v,n):
 if not isinstance(v,Mapping):raise TypeError(n)
 r={}
 for k,x in v.items():
  i=normalize_market_identity(*k) if isinstance(k,tuple) and len(k)==2 else None
  if i not in SUPPORTED_MARKET_IDENTITIES or not isinstance(x,tuple) or any(y not in _COMP for y in x) or len(x)!=len(set(x)):raise ValueError(n)
  r[i]=tuple(sorted(x))
 return MappingProxyType(dict(sorted(r.items())))
@dataclass(frozen=True,slots=True)
class MarketRegimePolicyV1:
 required_components:tuple[str,...]=( "TECHNICAL","MARKET_SESSION");optional_components:tuple[str,...]=( "BROADER_MARKET","EXTERNAL_CONTEXT")
 policy_name:str="INITIAL_CANONICAL_MARKET_REGIME_POLICY";required_components_by_identity:Mapping[tuple[str,str],tuple[str,...]]=field(default_factory=lambda:{i:("MARKET_SESSION","TECHNICAL") for i in SUPPORTED_MARKET_IDENTITIES});optional_components_by_identity:Mapping[tuple[str,str],tuple[str,...]]=field(default_factory=lambda:{i:("BROADER_MARKET","EXTERNAL_CONTEXT") for i in SUPPORTED_MARKET_IDENTITIES});minimum_available_component_count:int=1;fail_closed_on_invalid_mandatory_component:bool=True;warn_on_missing_optional_component:bool=True;block_on_missing_required_component:bool=True;block_on_blocked_required_component:bool=True;maximum_component_age_seconds:Mapping[str,float]=field(default_factory=lambda:{"TECHNICAL":300.,"BROADER_MARKET":600.,"EXTERNAL_CONTEXT":900.,"MARKET_SESSION":300.});future_timestamp_tolerance_seconds:float=5.;maximum_component_timestamp_skew_seconds:float=900.;block_on_stale_required_component:bool=True;warn_on_stale_optional_component:bool=True;block_on_future_required_component:bool=True;warn_on_future_optional_component:bool=True;technical_weight:float=.60;broader_market_weight:float=.25;external_context_weight:float=.15;bullish_strength_threshold:float=.55;strong_bullish_strength_threshold:float=.75;bearish_strength_threshold:float=.55;strong_bearish_strength_threshold:float=.75;minimum_regime_confidence:float=.50;strong_regime_confidence_threshold:float=.75;caution_confidence_threshold:float=.50;suitable_confidence_threshold:float=.70;minimum_confirmation_count:int=1;conflict_penalty:float=.20;warning_penalty:float=.05;partial_confirmation_penalty:float=.10;range_bound_strength_max:float=.20;directional_strength_min:float=.40;strong_directional_strength_min:float=.70;minimum_confirming_component_count:int=1;minimum_strong_regime_confirming_count:int=2;maximum_conflicting_component_count_for_ready:int=0;confirmation_strength_threshold:float=.55;partial_confirmation_strength_threshold:float=.35;technical_conflict_penalty:float=.20;broader_market_conflict_penalty:float=.15;external_context_conflict_penalty:float=.15;missing_optional_component_penalty:float=.05;partial_evidence_penalty:float=.10;high_volatility_override_states:tuple[str,...]=( "HIGH","EXTREME");high_volatility_confidence_penalty:float=.10;extreme_volatility_confidence_penalty:float=.25;high_volatility_entry_suitability:str="SUITABLE_WITH_WARNINGS";extreme_volatility_entry_suitability:str="NOT_SUITABLE";block_on_extreme_volatility:bool=False;event_risk_override_states:tuple[str,...]=( "HIGH","EXTREME");blocking_event_risk_states:tuple[str,...]=( "EXTREME",);block_when_analysis_disallowed:bool=True;preserve_session_owned_restriction:bool=True;use_most_restrictive_entry_policy:bool=True;block_on_required_component_failure:bool=True;warn_on_optional_component_failure:bool=True;aggregate_status_precedence:tuple[str,...]=( "BLOCKED","EVENT_RISK","CONFLICTING","HIGH_VOLATILITY","UNAVAILABLE","DIRECTIONAL");metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="market_regime_policy.v1"
 def __post_init__(self):
  object.__setattr__(self,"required_components_by_identity",_maps(self.required_components_by_identity,"required"));object.__setattr__(self,"optional_components_by_identity",_maps(self.optional_components_by_identity,"optional"))
  for n in ("required_components","optional_components"):
   v=getattr(self,n)
   if not isinstance(v,tuple) or any(type(x) is not str or x not in _COMP for x in v) or len(v)!=len(set(v)):raise ValueError(n)
   object.__setattr__(self,n,tuple(x for x in ("TECHNICAL","BROADER_MARKET","EXTERNAL_CONTEXT","MARKET_SESSION") if x in v))
  if set(self.required_components)&set(self.optional_components) or set(self.required_components)|set(self.optional_components)!=_COMP:raise ValueError("component ownership")
  if any(set(self.required_components_by_identity.get(i,()))&set(self.optional_components_by_identity.get(i,())) for i in set(self.required_components_by_identity)|set(self.optional_components_by_identity)):raise ValueError("overlap")
  if not isinstance(self.minimum_available_component_count,int) or not 0<=self.minimum_available_component_count<=4:raise ValueError("minimum")
  for n in ("future_timestamp_tolerance_seconds","maximum_component_timestamp_skew_seconds"):
   value=getattr(self,n)
   if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(float(value)) or value<0:raise ValueError(n)
   object.__setattr__(self,n,float(value))
  if not isinstance(self.maximum_component_age_seconds,Mapping):raise TypeError("ages")
  ages={}
  for key,value in self.maximum_component_age_seconds.items():
   if type(key) is not str or key not in _COMP or isinstance(value,bool) or not isinstance(value,(int,float)):raise ValueError("ages")
   value=float(value)
   if not math.isfinite(value) or value<=0:raise ValueError("ages")
   ages[key]=value
  if set(ages)!=_COMP:raise ValueError("ages")
  object.__setattr__(self,"maximum_component_age_seconds",MappingProxyType({key:ages[key] for key in ("TECHNICAL","BROADER_MARKET","EXTERNAL_CONTEXT","MARKET_SESSION")}))
  for n in ("technical_weight","broader_market_weight","external_context_weight"):
   object.__setattr__(self,n,_aggregate_weight(getattr(self,n),n))
  for n in ("bullish_strength_threshold","strong_bullish_strength_threshold","bearish_strength_threshold","strong_bearish_strength_threshold","minimum_regime_confidence","strong_regime_confidence_threshold","caution_confidence_threshold","suitable_confidence_threshold","conflict_penalty","missing_optional_component_penalty","warning_penalty","partial_confirmation_penalty"):
   object.__setattr__(self,n,_unit(getattr(self,n),n))
  if self.strong_bullish_strength_threshold<self.bullish_strength_threshold or self.strong_bearish_strength_threshold<self.bearish_strength_threshold or self.strong_regime_confidence_threshold<self.minimum_regime_confidence or self.suitable_confidence_threshold<self.caution_confidence_threshold:raise ValueError("threshold ordering")
  if type(self.minimum_confirmation_count) is not int or self.minimum_confirmation_count<0:raise ValueError("minimum_confirmation_count")
  for n in ("range_bound_strength_max","directional_strength_min","strong_directional_strength_min","confirmation_strength_threshold","partial_confirmation_strength_threshold","technical_conflict_penalty","broader_market_conflict_penalty","external_context_conflict_penalty","missing_optional_component_penalty","partial_evidence_penalty","high_volatility_confidence_penalty","extreme_volatility_confidence_penalty"):
   object.__setattr__(self,n,_unit(getattr(self,n),n))
  if not any((self.technical_weight,self.broader_market_weight,self.external_context_weight)) or not self.range_bound_strength_max<self.directional_strength_min<self.strong_directional_strength_min or self.partial_confirmation_strength_threshold>self.confirmation_strength_threshold:raise ValueError("thresholds")
  states=self.high_volatility_override_states
  if not isinstance(states,tuple) or not states or any(type(state) is not str or state not in {"HIGH","EXTREME"} for state in states) or len(states)!=len(set(states)):raise ValueError("high_volatility_override_states")
  object.__setattr__(self,"high_volatility_override_states",tuple(state for state in ("HIGH","EXTREME") if state in states))
  if self.high_volatility_entry_suitability not in _ENTRY or self.extreme_volatility_entry_suitability not in _ENTRY:raise ValueError("volatility")
  for n in ("block_when_analysis_disallowed","preserve_session_owned_restriction","use_most_restrictive_entry_policy","block_on_required_component_failure","warn_on_optional_component_failure"):
   if type(getattr(self,n)) is not bool:raise ValueError(n)
  for n in ("event_risk_override_states","blocking_event_risk_states"):
   states=getattr(self,n)
   if not isinstance(states,tuple) or not states or any(type(state) is not str or state not in _EVENT for state in states) or len(states)!=len(set(states)) or {"NONE","UNAVAILABLE"}&set(states):raise ValueError(n)
   object.__setattr__(self,n,tuple(state for state in _EVENT if state in states))
  if not set(self.blocking_event_risk_states)<=set(self.event_risk_override_states):raise ValueError("blocking_event_risk_states")
  precedence=self.aggregate_status_precedence
  if not isinstance(precedence,tuple) or any(type(state) is not str or state not in _PRECEDENCE for state in precedence) or len(precedence)!=len(set(precedence)) or set(precedence)!=set(_PRECEDENCE) or precedence!=_PRECEDENCE:raise ValueError("aggregate_status_precedence")
  object.__setattr__(self,"metadata",MappingProxyType(json.loads(json.dumps(dict(self.metadata),sort_keys=True,allow_nan=False))))
  if self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="market_regime_policy.v1":raise ValueError("paper")
 def to_dict(self):
  d={n:getattr(self,n) for n in self.__dataclass_fields__}
  for n in ("required_components_by_identity","optional_components_by_identity"):d[n]=[[list(i),list(v)] for i,v in getattr(self,n).items()]
  d["maximum_component_age_seconds"]=dict(self.maximum_component_age_seconds);d["metadata"]=dict(self.metadata);return d
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"))
 def semantic_dict(self):return self.to_dict()
 @property
 def high_volatility_state_values(self):return self.high_volatility_override_states
 @property
 def extreme_volatility_state_values(self):return ("EXTREME",)
 @property
 def component_weights(self):return MappingProxyType({"TECHNICAL":self.technical_weight,"BROADER_MARKET":self.broader_market_weight,"EXTERNAL_CONTEXT":self.external_context_weight})
DEFAULT_MARKET_REGIME_POLICY=MarketRegimePolicyV1()
