"""Immutable result for scheduled-event risk context."""
from __future__ import annotations
import json
from dataclasses import dataclass,field
from datetime import datetime
from types import MappingProxyType
from typing import Any,Mapping
from services.contracts.scheduled_market_event_v1 import ScheduledMarketEventV1
from services.core.market_identity import normalize_market_identity
_S={"READY","READY_WITH_WARNINGS","UNAVAILABLE","BLOCKED"};_R={"NONE","LOW","MODERATE","HIGH","EXTREME","UNAVAILABLE"};_E={"OPEN","WARNING","BLOCKED","SESSION_OWNED","UNAVAILABLE"}
def _x(v,n,u=False):
 if not isinstance(v,str) or not (v:=" ".join(v.split())):raise ValueError(f"{n} must be non-empty")
 return v.upper() if u else v
def _t(v,n):
 if not isinstance(v,datetime) or v.tzinfo is None or v.utcoffset() is None:raise ValueError(f"{n} must be timezone-aware")
 return v
def _m(v,n):
 if not isinstance(v,tuple):raise TypeError(f"{n} must be tuple")
 v=tuple(_x(x,n,True) for x in v)
 if len(v)!=len(set(v)) or v!=tuple(sorted(v)):raise ValueError(f"{n} must be ordered")
 return v
@dataclass(frozen=True,slots=True)
class EventRiskContextResultV1:
 event_risk_context_result_id:str;created_at:datetime;underlying_symbol:str;exchange:str;events:tuple[ScheduledMarketEventV1,...];context_status:str;event_risk_level:str;entry_restriction_state:str;analysis_allowed:bool;new_entries_allowed:bool;active_event_count:int;upcoming_event_count:int;cooldown_event_count:int;blocking_event_count:int;warning_event_count:int;highest_severity:str;active_event_ids:tuple[str,...]=();upcoming_event_ids:tuple[str,...]=();cooldown_event_ids:tuple[str,...]=();blocking_event_ids:tuple[str,...]=();supporting_evidence:tuple[str,...]=();contradictions:tuple[str,...]=();blockers:tuple[str,...]=();warnings:tuple[str,...]=();source_timestamps:Mapping[str,datetime]=field(default_factory=dict);metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="event_risk_context_result.v1"
 def __post_init__(self):
  object.__setattr__(self,"event_risk_context_result_id",_x(self.event_risk_context_result_id,"id"));object.__setattr__(self,"created_at",_t(self.created_at,"created_at"));i=normalize_market_identity(self.underlying_symbol,self.exchange)
  if i is None:raise ValueError("unsupported market identity")
  object.__setattr__(self,"underlying_symbol",i[0]);object.__setattr__(self,"exchange",i[1])
  if not isinstance(self.events,tuple) or any(not isinstance(e,ScheduledMarketEventV1) for e in self.events):raise TypeError("events must contain ScheduledMarketEventV1")
  ids=tuple(e.scheduled_market_event_id for e in self.events)
  if len(ids)!=len(set(ids)) or ids!=tuple(sorted(ids)) or any((e.affected_market_identities and i not in e.affected_market_identities) or (e.affected_exchanges and i[1] not in e.affected_exchanges) for e in self.events):raise ValueError("events are invalid or non-applicable")
  for n,a in (("context_status",_S),("event_risk_level",_R),("entry_restriction_state",_E),("highest_severity",_R)):
   v=_x(getattr(self,n),n,True)
   if v not in a:raise ValueError(f"unsupported {n}")
   object.__setattr__(self,n,v)
  if not isinstance(self.analysis_allowed,bool) or not isinstance(self.new_entries_allowed,bool) or (not self.analysis_allowed and self.new_entries_allowed):raise ValueError("analysis/entry flags inconsistent")
  for n in ("active_event_count","upcoming_event_count","cooldown_event_count","blocking_event_count","warning_event_count"):
   if not isinstance(getattr(self,n),int) or getattr(self,n)<0:raise ValueError("counts invalid")
  for n,c in (("active_event_ids","active_event_count"),("upcoming_event_ids","upcoming_event_count"),("cooldown_event_ids","cooldown_event_count"),("blocking_event_ids","blocking_event_count")):
   object.__setattr__(self,n,_m(getattr(self,n),n));
   if len(getattr(self,n))!=getattr(self,c):raise ValueError("event ids/counts inconsistent")
  for n in ("supporting_evidence","contradictions","blockers","warnings"):object.__setattr__(self,n,_m(getattr(self,n),n))
  s={_x(k,"source",True):_t(v,"source") for k,v in self.source_timestamps.items()}
  if tuple(s)!=tuple(sorted(s)):raise ValueError("source timestamps unordered")
  object.__setattr__(self,"source_timestamps",MappingProxyType(s));object.__setattr__(self,"metadata",MappingProxyType(json.loads(json.dumps(dict(self.metadata),sort_keys=True,allow_nan=False))))
  if self.context_status=="BLOCKED" and not self.blockers:raise ValueError("BLOCKED requires blockers")
  if self.context_status=="READY" and (self.warnings or self.blockers):raise ValueError("READY inconsistent")
  if self.context_status=="READY_WITH_WARNINGS" and not self.warnings:raise ValueError("warnings required")
  if self.context_status=="UNAVAILABLE" and (self.entry_restriction_state=="BLOCKED" or self.blocking_event_count):raise ValueError("unavailable cannot block")
  if self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="event_risk_context_result.v1":raise ValueError("paper only")
 def to_dict(self):
  d={n:getattr(self,n) for n in self.__dataclass_fields__};d["created_at"]=self.created_at.isoformat();d["events"]=[e.to_dict() for e in self.events]
  for n in ("active_event_ids","upcoming_event_ids","cooldown_event_ids","blocking_event_ids","supporting_evidence","contradictions","blockers","warnings"):d[n]=list(getattr(self,n))
  d["source_timestamps"]={k:v.isoformat() for k,v in self.source_timestamps.items()};d["metadata"]=dict(self.metadata);return d
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
 def semantic_dict(self):d=self.to_dict();d.pop("event_risk_context_result_id");d.pop("created_at");return d
