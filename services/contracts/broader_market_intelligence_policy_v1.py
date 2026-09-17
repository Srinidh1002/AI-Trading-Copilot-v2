"""Deterministic policy for future supplied broader-market intelligence."""
from __future__ import annotations
import json, math
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping
from services.core.market_identity import normalize_market_identity

_PAIRS=frozenset({(("NIFTY","NSE"),("SENSEX","BSE")),(("SENSEX","BSE"),("NIFTY","NSE")),(("BANKNIFTY","NSE"),("FINNIFTY","NSE")),(("FINNIFTY","NSE"),("BANKNIFTY","NSE"))})
_BEHAVIORS=frozenset({"BLOCK","WARN","ALLOW"})
_CONFLICTING=frozenset({"CONFLICTING","WARN"})
def _text(v:object,n:str,upper:bool=False)->str:
 if not isinstance(v,str):raise TypeError(f"{n} must be a string")
 v=v.strip()
 if not v:raise ValueError(f"{n} must not be empty")
 return v.upper() if upper else v
def _finite(v:object,n:str)->float:
 if isinstance(v,bool) or not isinstance(v,(int,float)):raise TypeError(f"{n} must be numeric")
 v=float(v)
 if not math.isfinite(v):raise ValueError(f"{n} must be finite")
 return v
def _unit(v:object,n:str)->float:
 v=_finite(v,n)
 if not 0<=v<=1:raise ValueError(f"{n} must be between zero and one")
 return v
def _nonnegative(v:object,n:str)->float:
 v=_finite(v,n)
 if v<0:raise ValueError(f"{n} must be non-negative")
 return v
def _boolean(v:object,n:str)->bool:
 if not isinstance(v,bool):raise TypeError(f"{n} must be a boolean")
 return v
def _relationships(v:object)->Mapping[tuple[str,str],tuple[tuple[str,str],...]]:
 if not isinstance(v,Mapping):raise TypeError("required_cross_market_relationships must be a mapping")
 result={}
 for primary, related_items in v.items():
  if not isinstance(primary,tuple) or len(primary)!=2:raise TypeError("relationship primary identity must be a two-item tuple")
  p=normalize_market_identity(*primary)
  if p is None:raise ValueError("unsupported relationship primary identity")
  if not isinstance(related_items,tuple) or not related_items:raise ValueError("relationship related identities must be a non-empty tuple")
  related=[]
  for item in related_items:
   if not isinstance(item,tuple) or len(item)!=2:raise TypeError("relationship related identity must be a two-item tuple")
   r=normalize_market_identity(*item)
   if r is None or r==p or (p,r) not in _PAIRS:raise ValueError("unsupported cross-market relationship")
   if r in related:raise ValueError("duplicate cross-market relationship")
   related.append(r)
  result[p]=tuple(related)
 if len(result)!=len(v):raise ValueError("duplicate relationship primary identity")
 return MappingProxyType(dict(sorted(result.items())))
def _metadata(v:object)->Mapping[str,Any]:
 if not isinstance(v,Mapping):raise TypeError("metadata must be a mapping")
 try:return MappingProxyType(json.loads(json.dumps(dict(v),sort_keys=True,allow_nan=False)))
 except (TypeError,ValueError) as e:raise ValueError("metadata must be JSON-safe") from e

@dataclass(frozen=True,slots=True)
class BroaderMarketIntelligencePolicyV1:
 policy_name:str="INITIAL_CANONICAL_BROADER_MARKET_INTELLIGENCE_POLICY"
 required_cross_market_relationships:Mapping[tuple[str,str],tuple[tuple[str,str],...]]=field(default_factory=lambda:{("NIFTY","NSE"):(("SENSEX","BSE"),),("SENSEX","BSE"):(("NIFTY","NSE"),),("BANKNIFTY","NSE"):(("FINNIFTY","NSE"),),("FINNIFTY","NSE"):(("BANKNIFTY","NSE"),)})
 require_cross_market_evidence:bool=True;require_breadth_evidence:bool=False;require_volatility_context:bool=False;allow_missing_optional_evidence:bool=True;minimum_available_component_count:int=1
 minimum_correlation_sample_size:int=30;minimum_correlation_lookback:int=30;strong_positive_correlation_threshold:float=.70;moderate_positive_correlation_threshold:float=.40;weak_correlation_absolute_threshold:float=.20;moderate_negative_correlation_threshold:float=-.40;strong_negative_correlation_threshold:float=-.70;minimum_confirmation_strength:float=.40;divergence_warning_strength:float=.50;divergence_block_strength:float=.80;block_on_strong_directional_divergence:bool=False
 minimum_breadth_coverage_ratio:float=.70;bullish_advance_decline_ratio:float=1.20;bearish_advance_decline_ratio:float=.80;strong_breadth_strength_threshold:float=.60;require_heavyweight_confirmation:bool=False;block_on_heavyweight_opposition:bool=False
 warn_on_high_volatility:bool=True;block_on_extreme_volatility:bool=False;reduce_confidence_on_rising_volatility:bool=True
 maximum_cross_market_age_seconds:float=300.;maximum_breadth_age_seconds:float=300.;maximum_volatility_age_seconds:float=300.;future_timestamp_tolerance_seconds:float=5.;maximum_cross_market_timestamp_skew_seconds:float=60.;require_same_timeframe:bool=True;allow_partial_candle_evidence:bool=False
 cross_market_weight:float=.60;breadth_weight:float=.25;volatility_weight:float=.15;confirmation_bonus:float=.05;divergence_penalty:float=.10;missing_optional_component_penalty:float=.0
 block_on_stale_mandatory_evidence:bool=True;block_on_future_mandatory_evidence:bool=True;block_on_misaligned_mandatory_evidence:bool=True;warn_on_stale_optional_evidence:bool=True;warn_on_missing_optional_evidence:bool=True;conflicting_bias_status:str="CONFLICTING";metadata:Mapping[str,Any]=field(default_factory=dict)
 execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="broader_market_intelligence_policy.v1"
 def __post_init__(self):
  object.__setattr__(self,"policy_name",_text(self.policy_name,"policy_name"));object.__setattr__(self,"required_cross_market_relationships",_relationships(self.required_cross_market_relationships))
  for n in ("require_cross_market_evidence","require_breadth_evidence","require_volatility_context","allow_missing_optional_evidence","block_on_strong_directional_divergence","require_heavyweight_confirmation","block_on_heavyweight_opposition","warn_on_high_volatility","block_on_extreme_volatility","reduce_confidence_on_rising_volatility","require_same_timeframe","allow_partial_candle_evidence","block_on_stale_mandatory_evidence","block_on_future_mandatory_evidence","block_on_misaligned_mandatory_evidence","warn_on_stale_optional_evidence","warn_on_missing_optional_evidence"):_boolean(getattr(self,n),n)
  if self.require_cross_market_evidence and not self.required_cross_market_relationships:raise ValueError("mandatory cross-market evidence requires relationships")
  if isinstance(self.minimum_available_component_count,bool) or not isinstance(self.minimum_available_component_count,int):raise TypeError("minimum_available_component_count must be an integer")
  if not 1<=self.minimum_available_component_count<=3:raise ValueError("minimum_available_component_count must be between one and three")
  for n in ("minimum_correlation_sample_size","minimum_correlation_lookback"):
   v=getattr(self,n)
   if isinstance(v,bool) or not isinstance(v,int):raise TypeError(f"{n} must be an integer")
   if v<=0:raise ValueError(f"{n} must be positive")
  if self.minimum_correlation_lookback<self.minimum_correlation_sample_size:raise ValueError("minimum_correlation_lookback must cover minimum sample size")
  for n in ("strong_positive_correlation_threshold","moderate_positive_correlation_threshold","weak_correlation_absolute_threshold","minimum_confirmation_strength","divergence_warning_strength","divergence_block_strength","minimum_breadth_coverage_ratio","strong_breadth_strength_threshold","cross_market_weight","breadth_weight","volatility_weight","confirmation_bonus","divergence_penalty","missing_optional_component_penalty"):object.__setattr__(self,n,_unit(getattr(self,n),n))
  for n in ("moderate_negative_correlation_threshold","strong_negative_correlation_threshold"):
   v=_finite(getattr(self,n),n)
   if not -1<=v<=0:raise ValueError(f"{n} must be between minus one and zero")
   object.__setattr__(self,n,v)
  if not (self.strong_negative_correlation_threshold<self.moderate_negative_correlation_threshold<-self.weak_correlation_absolute_threshold<self.weak_correlation_absolute_threshold<self.moderate_positive_correlation_threshold<self.strong_positive_correlation_threshold):raise ValueError("correlation thresholds are not strictly ordered")
  if self.divergence_block_strength<self.divergence_warning_strength:raise ValueError("divergence blocker threshold must not be weaker than warning threshold")
  for n in ("bullish_advance_decline_ratio","bearish_advance_decline_ratio"):object.__setattr__(self,n,_nonnegative(getattr(self,n),n))
  if not self.bearish_advance_decline_ratio<1<self.bullish_advance_decline_ratio:raise ValueError("breadth ratios must straddle one")
  for n in ("maximum_cross_market_age_seconds","maximum_breadth_age_seconds","maximum_volatility_age_seconds","future_timestamp_tolerance_seconds","maximum_cross_market_timestamp_skew_seconds"):object.__setattr__(self,n,_nonnegative(getattr(self,n),n))
  if not math.isclose(self.cross_market_weight+self.breadth_weight+self.volatility_weight,1.,abs_tol=1e-12):raise ValueError("base component weights must sum to exactly one")
  if not any((self.cross_market_weight,self.breadth_weight,self.volatility_weight)):raise ValueError("component weights cannot all be zero")
  status=_text(self.conflicting_bias_status,"conflicting_bias_status",True)
  if status not in _CONFLICTING:raise ValueError("unsupported conflicting_bias_status")
  object.__setattr__(self,"conflicting_bias_status",status);object.__setattr__(self,"metadata",_metadata(self.metadata))
  if self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="broader_market_intelligence_policy.v1":raise ValueError("broader-market policy is paper-only v1")
 def to_dict(self)->dict[str,Any]:
  return {"schema_version":self.schema_version,"policy_name":self.policy_name,"required_cross_market_relationships":[[[p[0],p[1]],[[r[0],r[1]] for r in related]] for p,related in self.required_cross_market_relationships.items()],**{n:getattr(self,n) for n in self.__dataclass_fields__ if n not in {"policy_name","required_cross_market_relationships","metadata","schema_version"}},"metadata":dict(self.metadata)}
 def to_json(self)->str:return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
 def semantic_dict(self)->dict[str,Any]:return self.to_dict()

DEFAULT_BROADER_MARKET_INTELLIGENCE_POLICY=BroaderMarketIntelligencePolicyV1()
