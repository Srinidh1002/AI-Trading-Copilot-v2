"""Immutable aggregate of already-evaluated external context components."""
from __future__ import annotations
import json,math
from dataclasses import dataclass,field
from datetime import datetime
from types import MappingProxyType
from typing import Any,Mapping
from services.contracts.global_market_context_result_v1 import GlobalMarketContextResultV1
from services.contracts.institutional_flow_context_result_v1 import InstitutionalFlowContextResultV1
from services.contracts.event_risk_context_result_v1 import EventRiskContextResultV1
from services.core.market_identity import normalize_market_identity
_S={"READY","READY_WITH_WARNINGS","CONFLICTING","UNAVAILABLE","BLOCKED"};_D={"POSITIVE","NEGATIVE","FLAT","CONFLICTING","UNAVAILABLE"};_C={"CONFIRMING","PARTIAL","NOT_CONFIRMING","CONFLICTING","UNAVAILABLE"};_R={"NONE","LOW","MODERATE","HIGH","EXTREME","UNAVAILABLE"};_E={"OPEN","WARNING","BLOCKED","SESSION_OWNED","UNAVAILABLE"}
def _t(v,n,u=False):
 if not isinstance(v,str) or not (v:=" ".join(v.split())):raise ValueError(f"{n} invalid")
 return v.upper() if u else v
@dataclass(frozen=True,slots=True)
class ExternalMarketContextResultV1:
 external_market_context_result_id:str;created_at:datetime;underlying_symbol:str;exchange:str;global_context:GlobalMarketContextResultV1|None;institutional_context:InstitutionalFlowContextResultV1|None;event_context:EventRiskContextResultV1|None;context_status:str;aggregate_direction:str;aggregate_strength:float;confirmation_state:str;risk_level:str;entry_restriction_state:str;analysis_allowed:bool;new_entries_allowed:bool;available_component_count:int;unavailable_component_count:int;confirming_component_count:int;conflicting_component_count:int;supporting_evidence:tuple[str,...]=();contradictions:tuple[str,...]=();blockers:tuple[str,...]=();warnings:tuple[str,...]=();source_timestamps:Mapping[str,datetime]=field(default_factory=dict);metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="external_market_context_result.v1"
 def __post_init__(self):
  object.__setattr__(self,"external_market_context_result_id",_t(self.external_market_context_result_id,"id"));
  if not isinstance(self.created_at,datetime) or self.created_at.tzinfo is None:raise ValueError("created_at aware")
  i=normalize_market_identity(self.underlying_symbol,self.exchange)
  if i is None:raise ValueError("identity")
  object.__setattr__(self,"underlying_symbol",i[0]);object.__setattr__(self,"exchange",i[1])
  for c,typ in ((self.global_context,GlobalMarketContextResultV1),(self.institutional_context,InstitutionalFlowContextResultV1),(self.event_context,EventRiskContextResultV1)):
   if c is not None and (not isinstance(c,typ) or (c.underlying_symbol,c.exchange)!=i):raise ValueError("component mismatch")
  for n,a in (("context_status",_S),("aggregate_direction",_D),("confirmation_state",_C),("risk_level",_R),("entry_restriction_state",_E)):
   v=_t(getattr(self,n),n,True)
   if v not in a:raise ValueError("vocabulary")
   object.__setattr__(self,n,v)
  if not isinstance(self.aggregate_strength,(int,float)) or not math.isfinite(self.aggregate_strength) or not 0<=self.aggregate_strength<=1:raise ValueError("strength")
  if not self.analysis_allowed and self.new_entries_allowed:raise ValueError("flags")
  if any(not isinstance(getattr(self,n),int) or getattr(self,n)<0 for n in ("available_component_count","unavailable_component_count","confirming_component_count","conflicting_component_count")) or self.available_component_count+self.unavailable_component_count!=3:raise ValueError("counts")
  for n in ("supporting_evidence","contradictions","blockers","warnings"):
   v=tuple(sorted(set(_t(x,n,True) for x in getattr(self,n))));object.__setattr__(self,n,v)
  s={_t(k,"source",True):v for k,v in self.source_timestamps.items()}
  if any(not isinstance(v,datetime) or v.tzinfo is None for v in s.values()):raise ValueError("timestamps")
  object.__setattr__(self,"source_timestamps",MappingProxyType(dict(sorted(s.items()))));object.__setattr__(self,"metadata",MappingProxyType(json.loads(json.dumps(dict(self.metadata),sort_keys=True,allow_nan=False))))
  if self.context_status=="BLOCKED" and not self.blockers:raise ValueError("blockers")
  if self.context_status=="CONFLICTING" and not self.contradictions:raise ValueError("contradictions")
  if self.context_status=="UNAVAILABLE" and (self.aggregate_strength or self.aggregate_direction!="UNAVAILABLE"):raise ValueError("unavailable")
  if self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="external_market_context_result.v1":raise ValueError("paper")
 def to_dict(self):
  d={n:getattr(self,n) for n in self.__dataclass_fields__};d["created_at"]=self.created_at.isoformat()
  for n in ("global_context","institutional_context","event_context"):d[n]=getattr(self,n).to_dict() if getattr(self,n) else None
  for n in ("supporting_evidence","contradictions","blockers","warnings"):d[n]=list(getattr(self,n))
  d["source_timestamps"]={k:v.isoformat() for k,v in self.source_timestamps.items()};d["metadata"]=dict(self.metadata);return d
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"))
 def semantic_dict(self):d=self.to_dict();d.pop("external_market_context_result_id");d.pop("created_at");return d
