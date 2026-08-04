"""Immutable contextual result for one institutional-flow snapshot."""
from __future__ import annotations
import json,math
from dataclasses import dataclass,field
from datetime import datetime
from types import MappingProxyType
from typing import Any,Mapping
from services.contracts.institutional_flow_snapshot_v1 import InstitutionalFlowSnapshotV1
from services.core.market_identity import normalize_market_identity
_S={"READY","READY_WITH_WARNINGS","CONFLICTING","UNAVAILABLE","BLOCKED"};_A={"POSITIVE","NEGATIVE","FLAT","CONFLICTING","UNAVAILABLE"};_C={"CONFIRMING","PARTIAL","NOT_CONFIRMING","CONFLICTING","UNAVAILABLE"};_D={"POSITIVE","NEGATIVE","FLAT","UNAVAILABLE"}
def _t(v,n,u=False):
 if not isinstance(v,str):raise TypeError(f"{n} must be a string")
 v=" ".join(v.split())
 if not v:raise ValueError(f"{n} must not be empty")
 return v.upper() if u else v
def _time(v,n):
 if not isinstance(v,datetime) or v.tzinfo is None or v.utcoffset() is None:raise ValueError(f"{n} must be timezone-aware")
 return v
def _msgs(v,n):
 if not isinstance(v,tuple):raise TypeError(f"{n} must be a tuple")
 x=tuple(_t(i,f"{n} item",True) for i in v)
 if len(x)!=len(set(x)) or x!=tuple(sorted(x)):raise ValueError(f"{n} must be unique and ordered")
 return x
@dataclass(frozen=True,slots=True)
class InstitutionalFlowContextResultV1:
 institutional_flow_context_result_id:str;created_at:datetime;underlying_symbol:str;exchange:str;snapshot:InstitutionalFlowSnapshotV1|None;context_status:str;aggregate_direction:str;aggregate_strength:float;confirmation_state:str;publication_state:str;session_reference:str;available_component_count:int;unavailable_component_count:int;cash_direction:str;derivatives_direction:str;fii_cash_direction:str;dii_cash_direction:str;fii_index_futures_direction:str;fii_index_options_direction:str;supporting_evidence:tuple[str,...]=();contradictions:tuple[str,...]=();blockers:tuple[str,...]=();warnings:tuple[str,...]=();source_timestamps:Mapping[str,datetime]=field(default_factory=dict);metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="institutional_flow_context_result.v1"
 def __post_init__(self):
  object.__setattr__(self,"institutional_flow_context_result_id",_t(self.institutional_flow_context_result_id,"institutional_flow_context_result_id"));object.__setattr__(self,"created_at",_time(self.created_at,"created_at"));identity=normalize_market_identity(self.underlying_symbol,self.exchange)
  if identity is None:raise ValueError("unsupported market identity")
  object.__setattr__(self,"underlying_symbol",identity[0]);object.__setattr__(self,"exchange",identity[1])
  if self.snapshot is not None:
   if not isinstance(self.snapshot,InstitutionalFlowSnapshotV1):raise TypeError("snapshot must be InstitutionalFlowSnapshotV1 or None")
   if self.snapshot.affected_market_identities and identity not in self.snapshot.affected_market_identities:raise ValueError("snapshot does not apply to result identity")
   if self.publication_state!=self.snapshot.publication_state or self.session_reference!=self.snapshot.session_reference:raise ValueError("snapshot publication/session must be copied exactly")
  elif self.publication_state!="UNAVAILABLE" or self.session_reference!="UNAVAILABLE":raise ValueError("missing snapshot requires unavailable publication/session")
  for n,a in (("context_status",_S),("aggregate_direction",_A),("confirmation_state",_C),("cash_direction",_D),("derivatives_direction",_D),("fii_cash_direction",_D),("dii_cash_direction",_D),("fii_index_futures_direction",_D),("fii_index_options_direction",_D)):
   v=_t(getattr(self,n),n,True)
   if v not in a:raise ValueError(f"unsupported {n}")
   object.__setattr__(self,n,v)
  if isinstance(self.aggregate_strength,bool) or not isinstance(self.aggregate_strength,(int,float)) or not math.isfinite(float(self.aggregate_strength)) or not 0<=float(self.aggregate_strength)<=1:raise ValueError("aggregate_strength must be finite between zero and one")
  object.__setattr__(self,"aggregate_strength",float(self.aggregate_strength))
  if any(isinstance(getattr(self,n),bool) or not isinstance(getattr(self,n),int) or getattr(self,n)<0 for n in ("available_component_count","unavailable_component_count")) or self.available_component_count+self.unavailable_component_count!=4:raise ValueError("component counts are inconsistent")
  for n in ("supporting_evidence","contradictions","blockers","warnings"):object.__setattr__(self,n,_msgs(getattr(self,n),n))
  if not isinstance(self.source_timestamps,Mapping):raise TypeError("source_timestamps must be a mapping")
  s={_t(k,"source timestamp key",True):_time(v,"source timestamp") for k,v in self.source_timestamps.items()}
  if tuple(s)!=tuple(sorted(s)) or (self.snapshot is None and s) or (self.snapshot is not None and s!={_t(self.snapshot.source_id,"source timestamp key",True):self.snapshot.source_timestamp}):raise ValueError("source_timestamps are inconsistent")
  object.__setattr__(self,"source_timestamps",MappingProxyType(s))
  try:m=json.loads(json.dumps(dict(self.metadata),sort_keys=True,allow_nan=False))
  except (TypeError,ValueError) as e:raise ValueError("metadata must be JSON-safe") from e
  object.__setattr__(self,"metadata",MappingProxyType(m))
  if self.context_status=="BLOCKED" and not self.blockers:raise ValueError("BLOCKED requires blockers")
  if self.context_status=="CONFLICTING" and not self.contradictions:raise ValueError("CONFLICTING requires contradictions")
  if self.context_status=="READY" and (not self.available_component_count or self.warnings or self.blockers or self.contradictions):raise ValueError("READY is contradictory")
  if self.context_status=="READY_WITH_WARNINGS" and not self.warnings:raise ValueError("READY_WITH_WARNINGS requires warnings")
  if self.context_status=="UNAVAILABLE" and (self.aggregate_direction!="UNAVAILABLE" or self.aggregate_strength!=0):raise ValueError("UNAVAILABLE cannot claim strength")
  if self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="institutional_flow_context_result.v1":raise ValueError("institutional context result is paper-only v1")
 def to_dict(self):
  d={n:getattr(self,n) for n in self.__dataclass_fields__};d["created_at"]=self.created_at.isoformat();d["snapshot"]=self.snapshot.to_dict() if self.snapshot else None
  for n in ("supporting_evidence","contradictions","blockers","warnings"):d[n]=list(getattr(self,n))
  d["source_timestamps"]={k:v.isoformat() for k,v in self.source_timestamps.items()};d["metadata"]=dict(self.metadata);return d
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
 def semantic_dict(self):d=self.to_dict();d.pop("institutional_flow_context_result_id");d.pop("created_at");return d
