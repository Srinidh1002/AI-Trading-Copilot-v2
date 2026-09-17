"""Immutable result of evaluating normalized global market observations."""
from __future__ import annotations
import json, math
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping
from services.contracts.external_market_observation_v1 import ExternalMarketObservationV1
from services.core.market_identity import normalize_market_identity

_STATUS={"READY","READY_WITH_WARNINGS","CONFLICTING","UNAVAILABLE","BLOCKED"};_DIRECTION={"POSITIVE","NEGATIVE","FLAT","CONFLICTING","UNAVAILABLE"};_CONFIRM={"CONFIRMING","PARTIAL","NOT_CONFIRMING","CONFLICTING","UNAVAILABLE"}
def _text(v,n,u=False):
 if not isinstance(v,str):raise TypeError(f"{n} must be a string")
 v=" ".join(v.split())
 if not v:raise ValueError(f"{n} must not be empty")
 return v.upper() if u else v
def _time(v,n):
 if not isinstance(v,datetime):raise TypeError(f"{n} must be a datetime")
 if v.tzinfo is None or v.utcoffset() is None:raise ValueError(f"{n} must be timezone-aware")
 return v
def _messages(v,n):
 if not isinstance(v,tuple):raise TypeError(f"{n} must be a tuple")
 x=tuple(_text(i,f"{n} item",True) for i in v)
 if len(x)!=len(set(x)) or x!=tuple(sorted(x)):raise ValueError(f"{n} must be unique and ordered")
 return x
def _meta(v):
 if not isinstance(v,Mapping):raise TypeError("metadata must be a mapping")
 try:return MappingProxyType(json.loads(json.dumps(dict(v),sort_keys=True,allow_nan=False)))
 except (TypeError,ValueError) as e:raise ValueError("metadata must be JSON-safe") from e
@dataclass(frozen=True,slots=True)
class GlobalMarketContextResultV1:
 global_market_context_result_id:str;created_at:datetime;underlying_symbol:str;exchange:str;observations:tuple[ExternalMarketObservationV1,...];context_status:str;aggregate_direction:str;aggregate_strength:float;confirmation_state:str;available_observation_count:int;unavailable_observation_count:int;delayed_observation_count:int;positive_weight:float;negative_weight:float;flat_weight:float;supporting_evidence:tuple[str,...]=();contradictions:tuple[str,...]=();blockers:tuple[str,...]=();warnings:tuple[str,...]=();source_timestamps:Mapping[str,datetime]=field(default_factory=dict);metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="global_market_context_result.v1"
 def __post_init__(self):
  object.__setattr__(self,"global_market_context_result_id",_text(self.global_market_context_result_id,"global_market_context_result_id"));object.__setattr__(self,"created_at",_time(self.created_at,"created_at"))
  identity=normalize_market_identity(self.underlying_symbol,self.exchange)
  if identity is None:raise ValueError("unsupported market identity")
  object.__setattr__(self,"underlying_symbol",identity[0]);object.__setattr__(self,"exchange",identity[1])
  if not isinstance(self.observations,tuple):raise TypeError("observations must be a tuple")
  names=[]
  for item in self.observations:
   if not isinstance(item,ExternalMarketObservationV1):raise TypeError("observations must contain ExternalMarketObservationV1")
   if item.affected_market_identities and identity not in item.affected_market_identities:raise ValueError("observation does not apply to result identity")
   names.append(item.canonical_name)
  if len(names)!=len(set(names)) or tuple(names)!=tuple(sorted(names)):raise ValueError("observations must be unique and ordered")
  for n,a in (("context_status",_STATUS),("aggregate_direction",_DIRECTION),("confirmation_state",_CONFIRM)):
   v=_text(getattr(self,n),n,True)
   if v not in a:raise ValueError(f"unsupported {n}")
   object.__setattr__(self,n,v)
  for n in ("aggregate_strength","positive_weight","negative_weight","flat_weight"):
   v=getattr(self,n)
   if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(float(v)) or not 0<=float(v)<=1:raise ValueError(f"{n} must be finite between zero and one")
   object.__setattr__(self,n,float(v))
  for n in ("available_observation_count","unavailable_observation_count","delayed_observation_count"):
   v=getattr(self,n)
   if isinstance(v,bool) or not isinstance(v,int) or v<0:raise ValueError(f"{n} must be a non-negative integer")
  if self.available_observation_count+self.unavailable_observation_count!=len(self.observations) or self.delayed_observation_count>len(self.observations):raise ValueError("observation counts are inconsistent")
  for n in ("supporting_evidence","contradictions","blockers","warnings"):object.__setattr__(self,n,_messages(getattr(self,n),n))
  if not isinstance(self.source_timestamps,Mapping):raise TypeError("source_timestamps must be a mapping")
  stamps={}
  for k,v in self.source_timestamps.items():
   k=_text(k,"source timestamp key",True);stamps[k]=_time(v,"source timestamp")
  if tuple(stamps)!=tuple(sorted(stamps)) or set(stamps)!=set(names):raise ValueError("source_timestamps must exactly cover observations in order")
  object.__setattr__(self,"source_timestamps",MappingProxyType(stamps));object.__setattr__(self,"metadata",_meta(self.metadata))
  if self.context_status=="BLOCKED" and not self.blockers:raise ValueError("BLOCKED requires blockers")
  if self.context_status=="CONFLICTING" and not self.contradictions:raise ValueError("CONFLICTING requires contradictions")
  if self.context_status=="READY" and (not self.available_observation_count or self.blockers or self.contradictions or self.warnings):raise ValueError("READY is contradictory")
  if self.context_status=="READY_WITH_WARNINGS" and not self.warnings:raise ValueError("READY_WITH_WARNINGS requires warnings")
  if self.context_status=="UNAVAILABLE" and (self.aggregate_direction!="UNAVAILABLE" or self.aggregate_strength!=0):raise ValueError("UNAVAILABLE cannot claim directional strength")
  if self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="global_market_context_result.v1":raise ValueError("global context result is paper-only v1")
 def to_dict(self):
  d={n:getattr(self,n) for n in self.__dataclass_fields__};d["created_at"]=self.created_at.isoformat();d["observations"]=[x.to_dict() for x in self.observations]
  for n in ("supporting_evidence","contradictions","blockers","warnings"):d[n]=list(getattr(self,n))
  d["source_timestamps"]={k:v.isoformat() for k,v in self.source_timestamps.items()};d["metadata"]=dict(self.metadata);return d
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
 def semantic_dict(self):
  d=self.to_dict();d.pop("global_market_context_result_id");d.pop("created_at");return d
