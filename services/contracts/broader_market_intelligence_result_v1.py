"""Immutable aggregate broader-market evidence; no evaluation or decision."""
from __future__ import annotations
import json,math
from dataclasses import dataclass,field
from datetime import datetime
from types import MappingProxyType
from typing import Any,Mapping
from services.core.market_identity import normalize_market_identity
from .cross_market_evidence_v1 import CrossMarketEvidenceV1
from .market_breadth_evidence_v1 import MarketBreadthEvidenceV1
from .volatility_context_v1 import VolatilityContextV1
_S={"READY","READY_WITH_WARNINGS","INSUFFICIENT_DATA","STALE","UNAVAILABLE","BLOCKED","CONFLICTING"};_B={"BULLISH","BEARISH","NEUTRAL","CONFLICTING","UNAVAILABLE"};_C={"CONFIRMING","PARTIAL","NOT_CONFIRMING","UNAVAILABLE"};_D={"NONE","DIRECTIONAL_DIVERGENCE","UNAVAILABLE"}
def _text(v,n,u=False):
 if not isinstance(v,str):raise TypeError(f"{n} must be a string")
 v=v.strip()
 if not v:raise ValueError(f"{n} must not be empty")
 return v.upper() if u else v
def _msgs(v,n):
 if not isinstance(v,tuple):raise TypeError(f"{n} must be a tuple")
 v=tuple(_text(x,f"{n} item") for x in v)
 if len(v)!=len(set(v)):raise ValueError(f"{n} must not contain duplicates")
 return v
def _sources(v):
 if not isinstance(v,Mapping):raise TypeError("source_timestamps must be a mapping")
 result={}
 for key,item in v.items():
  key=_text(key,"source_timestamps key")
  if not isinstance(item,datetime):raise TypeError("source_timestamps values must be datetimes")
  if item.tzinfo is None or item.utcoffset() is None:raise ValueError("source_timestamps values must be timezone-aware")
  result[key]=item
 return MappingProxyType(dict(sorted(result.items())))
def _meta(v):
 if not isinstance(v,Mapping):raise TypeError("metadata must be a mapping")
 try:return MappingProxyType(json.loads(json.dumps(dict(v),sort_keys=True,allow_nan=False)))
 except (TypeError,ValueError) as e:raise ValueError("metadata must be JSON-safe") from e
@dataclass(frozen=True,slots=True)
class BroaderMarketIntelligenceResultV1:
 broader_market_intelligence_result_id:str;created_at:datetime;underlying_symbol:str;exchange:str;cross_market_evidence:tuple[CrossMarketEvidenceV1,...];breadth_evidence:MarketBreadthEvidenceV1|None;volatility_context:VolatilityContextV1|None
 intelligence_status:str;aggregate_bias:str;aggregate_strength:float;confirmation_state:str;divergence_state:str;available_component_count:int;unavailable_component_count:int
 supporting_evidence:tuple[str,...]=();contradictions:tuple[str,...]=();blockers:tuple[str,...]=();warnings:tuple[str,...]=();source_timestamps:Mapping[str,datetime]=field(default_factory=dict);metadata:Mapping[str,Any]=field(default_factory=dict)
 execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="broader_market_intelligence_result.v1"
 def __post_init__(self):
  object.__setattr__(self,"broader_market_intelligence_result_id",_text(self.broader_market_intelligence_result_id,"broader_market_intelligence_result_id"))
  if not isinstance(self.created_at,datetime):raise TypeError("created_at must be a datetime")
  if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:raise ValueError("created_at must be timezone-aware")
  identity=normalize_market_identity(self.underlying_symbol,self.exchange)
  if identity is None:raise ValueError("unsupported market identity")
  object.__setattr__(self,"underlying_symbol",identity[0]);object.__setattr__(self,"exchange",identity[1])
  if not isinstance(self.cross_market_evidence,tuple):raise TypeError("cross_market_evidence must be a tuple")
  pairs=set()
  for item in self.cross_market_evidence:
   if not isinstance(item,CrossMarketEvidenceV1):raise TypeError("cross_market_evidence must contain CrossMarketEvidenceV1")
   if (item.primary_symbol,item.primary_exchange)!=identity:raise ValueError("cross-market child identity must match result")
   pair=(item.related_symbol,item.related_exchange)
   if pair in pairs:raise ValueError("duplicate cross-market relationship")
   pairs.add(pair)
  if self.breadth_evidence is not None:
   if not isinstance(self.breadth_evidence,MarketBreadthEvidenceV1):raise TypeError("breadth_evidence must be MarketBreadthEvidenceV1 or None")
   if (self.breadth_evidence.underlying_symbol,self.breadth_evidence.exchange)!=identity:raise ValueError("breadth child identity must match result")
  if self.volatility_context is not None:
   if not isinstance(self.volatility_context,VolatilityContextV1):raise TypeError("volatility_context must be VolatilityContextV1 or None")
   if (self.volatility_context.underlying_symbol,self.volatility_context.exchange)!=identity:raise ValueError("volatility child identity must match result")
  for n,a in (("intelligence_status",_S),("aggregate_bias",_B),("confirmation_state",_C),("divergence_state",_D)):
   v=_text(getattr(self,n),n,True)
   if v not in a:raise ValueError(f"unsupported {n}")
   object.__setattr__(self,n,v)
  v=self.aggregate_strength
  if isinstance(v,bool) or not isinstance(v,(int,float)):raise TypeError("aggregate_strength must be numeric")
  v=float(v)
  if not math.isfinite(v) or not 0<=v<=1:raise ValueError("aggregate_strength must be between zero and one")
  object.__setattr__(self,"aggregate_strength",v)
  available=sum(x.evidence_status in {"READY","READY_WITH_WARNINGS"} for x in self.cross_market_evidence)+(self.breadth_evidence is not None and self.breadth_evidence.evidence_status in {"READY","READY_WITH_WARNINGS"})+(self.volatility_context is not None and self.volatility_context.context_status in {"READY","READY_WITH_WARNINGS"})
  total=len(self.cross_market_evidence)+(self.breadth_evidence is not None)+(self.volatility_context is not None)
  for n,expected in (("available_component_count",available),("unavailable_component_count",total-available)):
   value=getattr(self,n)
   if isinstance(value,bool) or not isinstance(value,int):raise TypeError(f"{n} must be an integer")
   if value!=expected:raise ValueError(f"{n} does not match child evidence")
  for n in ("supporting_evidence","contradictions","blockers","warnings"):object.__setattr__(self,n,_msgs(getattr(self,n),n))
  object.__setattr__(self,"source_timestamps",_sources(self.source_timestamps));object.__setattr__(self,"metadata",_meta(self.metadata))
  if self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="broader_market_intelligence_result.v1":raise ValueError("broader-market result is paper-only v1")
  if self.intelligence_status=="READY" and (not available or self.blockers or self.warnings or self.contradictions):raise ValueError("READY result is contradictory")
  if self.intelligence_status=="READY_WITH_WARNINGS" and (not available or self.blockers or not self.warnings):raise ValueError("READY_WITH_WARNINGS result is contradictory")
  if self.intelligence_status=="CONFLICTING" and not self.contradictions:raise ValueError("CONFLICTING requires contradictions")
  if self.intelligence_status in {"BLOCKED","INSUFFICIENT_DATA","STALE","UNAVAILABLE"} and (not self.blockers or self.aggregate_strength!=0 or self.aggregate_bias!="UNAVAILABLE"):raise ValueError("unavailable result must be explicit and blocked")
  if self.intelligence_status=="UNAVAILABLE" and self.aggregate_strength!=0:raise ValueError("UNAVAILABLE cannot have strength")
 def to_dict(self):
  return {"schema_version":self.schema_version,"broader_market_intelligence_result_id":self.broader_market_intelligence_result_id,"created_at":self.created_at.isoformat(),"underlying_symbol":self.underlying_symbol,"exchange":self.exchange,"cross_market_evidence":[x.to_dict() for x in self.cross_market_evidence],"breadth_evidence":self.breadth_evidence.to_dict() if self.breadth_evidence else None,"volatility_context":self.volatility_context.to_dict() if self.volatility_context else None,"intelligence_status":self.intelligence_status,"aggregate_bias":self.aggregate_bias,"aggregate_strength":self.aggregate_strength,"confirmation_state":self.confirmation_state,"divergence_state":self.divergence_state,"available_component_count":self.available_component_count,"unavailable_component_count":self.unavailable_component_count,"supporting_evidence":list(self.supporting_evidence),"contradictions":list(self.contradictions),"blockers":list(self.blockers),"warnings":list(self.warnings),"source_timestamps":{k:v.isoformat() for k,v in self.source_timestamps.items()},"metadata":dict(self.metadata),"execution_mode":self.execution_mode,"live_execution_eligible":self.live_execution_eligible}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
 def semantic_dict(self):d=self.to_dict();d.pop("broader_market_intelligence_result_id");d.pop("created_at");return d
