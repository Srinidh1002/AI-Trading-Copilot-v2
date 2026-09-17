"""Immutable normalized institutional-flow snapshot; no directional inference."""
from __future__ import annotations
import json,math
from dataclasses import dataclass,field
from datetime import date,datetime
from types import MappingProxyType
from typing import Any,Mapping
from services.core.market_identity import normalize_market_identity,SUPPORTED_MARKET_IDENTITIES
_P={"PROVISIONAL","FINAL","UNAVAILABLE"};_S={"CURRENT_SESSION","PREVIOUS_SESSION","END_OF_DAY","UNAVAILABLE"};_F={"READY","READY_WITH_WARNINGS","DELAYED","STALE","PARTIAL","UNAVAILABLE","BLOCKED"};_C={"INR"};_CASH={"RUPEES","CRORE_INR","UNAVAILABLE"};_DER={"CONTRACTS","NOTIONAL_CRORE_INR","MIXED_NORMALIZED","UNAVAILABLE"}
def _text(v,n,u=False):
 if not isinstance(v,str):raise TypeError(f"{n} must be a string")
 v=v.strip()
 if not v:raise ValueError(f"{n} must not be empty")
 return v.upper() if u else v
def _time(v,n):
 if not isinstance(v,datetime):raise TypeError(f"{n} must be a datetime")
 if v.tzinfo is None or v.utcoffset() is None:raise ValueError(f"{n} must be timezone-aware")
 return v
def _msgs(v,n):
 if not isinstance(v,tuple):raise TypeError(f"{n} must be a tuple")
 v=tuple(_text(x,f"{n} item") for x in v)
 if len(v)!=len(set(v)):raise ValueError(f"{n} must not contain duplicates")
 return v
def _meta(v):
 if not isinstance(v,Mapping):raise TypeError("metadata must be a mapping")
 try:return MappingProxyType(json.loads(json.dumps(dict(v),sort_keys=True,allow_nan=False)))
 except (TypeError,ValueError) as e:raise ValueError("metadata must be JSON-safe") from e
@dataclass(frozen=True,slots=True)
class InstitutionalFlowSnapshotV1:
 institutional_flow_snapshot_id:str;created_at:datetime;trading_date:date;source_id:str;source_timestamp:datetime;publication_state:str;session_reference:str;currency:str;cash_flow_unit:str;derivatives_position_unit:str;fii_cash_net:float|None;dii_cash_net:float|None;fii_index_futures_net:float|None;fii_index_options_net:float|None;flow_status:str;is_delayed:bool=False;delay_seconds:float=0.;affected_market_identities:tuple[tuple[str,str],...]=();blockers:tuple[str,...]=();warnings:tuple[str,...]=();metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="institutional_flow_snapshot.v1"
 def __post_init__(self):
  for n in ("institutional_flow_snapshot_id","source_id"):object.__setattr__(self,n,_text(getattr(self,n),n))
  object.__setattr__(self,"created_at",_time(self.created_at,"created_at"));object.__setattr__(self,"source_timestamp",_time(self.source_timestamp,"source_timestamp"))
  if isinstance(self.trading_date,datetime) or not isinstance(self.trading_date,date):raise TypeError("trading_date must be a date")
  for n,a in (("publication_state",_P),("session_reference",_S),("currency",_C),("cash_flow_unit",_CASH),("derivatives_position_unit",_DER),("flow_status",_F)):
   v=_text(getattr(self,n),n,True)
   if v not in a:raise ValueError(f"unsupported {n}")
   object.__setattr__(self,n,v)
  values=[]
  for n in ("fii_cash_net","dii_cash_net","fii_index_futures_net","fii_index_options_net"):
   v=getattr(self,n)
   if v is not None:
    if isinstance(v,bool) or not isinstance(v,(int,float)):raise TypeError(f"{n} must be numeric or None")
    v=float(v)
    if not math.isfinite(v):raise ValueError(f"{n} must be finite")
   object.__setattr__(self,n,v);values.append(v)
  if isinstance(self.delay_seconds,bool) or not isinstance(self.delay_seconds,(int,float)) or not math.isfinite(float(self.delay_seconds)) or self.delay_seconds<0:raise ValueError("delay_seconds must be finite and non-negative")
  if not isinstance(self.is_delayed,bool):raise TypeError("is_delayed must be boolean")
  if self.is_delayed!=(self.delay_seconds>0):raise ValueError("delay fields are inconsistent")
  identities=[]
  if not isinstance(self.affected_market_identities,tuple):raise TypeError("affected_market_identities must be a tuple")
  for x in self.affected_market_identities:
   if not isinstance(x,tuple) or len(x)!=2 or normalize_market_identity(*x) not in SUPPORTED_MARKET_IDENTITIES:raise ValueError("unsupported affected market identity")
   identities.append(normalize_market_identity(*x))
  if len(set(identities))!=len(identities) or tuple(identities)!=tuple(sorted(identities)):raise ValueError("affected identities must be unique and ordered")
  object.__setattr__(self,"affected_market_identities",tuple(identities));object.__setattr__(self,"blockers",_msgs(self.blockers,"blockers"));object.__setattr__(self,"warnings",_msgs(self.warnings,"warnings"));object.__setattr__(self,"metadata",_meta(self.metadata))
  usable=any(v is not None for v in values)
  if self.flow_status=="READY" and (not usable or self.blockers or self.warnings or self.is_delayed or self.publication_state!="FINAL"):raise ValueError("READY snapshot is contradictory")
  if self.flow_status in {"READY_WITH_WARNINGS","DELAYED","PARTIAL"} and (not usable or not self.warnings):raise ValueError("warning flow status requires values and warnings")
  if self.flow_status=="DELAYED" and not self.is_delayed:raise ValueError("DELAYED requires delay")
  if self.flow_status=="UNAVAILABLE" and usable:raise ValueError("UNAVAILABLE must not contain flow values")
  if self.flow_status=="BLOCKED" and not self.blockers:raise ValueError("BLOCKED requires blockers")
  if self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="institutional_flow_snapshot.v1":raise ValueError("institutional snapshot is paper-only v1")
 def to_dict(self):
  d={n:getattr(self,n) for n in self.__dataclass_fields__ if n not in {"created_at","source_timestamp","trading_date","affected_market_identities","blockers","warnings","metadata"}};d["created_at"]=self.created_at.isoformat();d["source_timestamp"]=self.source_timestamp.isoformat();d["trading_date"]=self.trading_date.isoformat();d["affected_market_identities"]=[list(x) for x in self.affected_market_identities];d["blockers"]=list(self.blockers);d["warnings"]=list(self.warnings);d["metadata"]=dict(self.metadata);return d
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
 def semantic_dict(self):d=self.to_dict();d.pop("institutional_flow_snapshot_id");d.pop("created_at");return d
