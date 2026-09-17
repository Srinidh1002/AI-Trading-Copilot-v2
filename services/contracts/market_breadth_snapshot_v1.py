"""Immutable normalized market-breadth input; no provider behavior."""
from __future__ import annotations
import json
from dataclasses import dataclass,field
from datetime import datetime
from types import MappingProxyType
from typing import Any,Mapping
from services.core.market_identity import normalize_market_identity
_H={"CONFIRMS","CONTRADICTS","NEUTRAL","UNAVAILABLE"}
def _text(v,n,u=False):
 if not isinstance(v,str):raise TypeError(f"{n} must be a string")
 v=v.strip()
 if not v:raise ValueError(f"{n} must not be empty")
 return v.upper() if u else v
def _time(v,n):
 if not isinstance(v,datetime):raise TypeError(f"{n} must be a datetime")
 if v.tzinfo is None or v.utcoffset() is None:raise ValueError(f"{n} must be timezone-aware")
 return v
def _messages(v,n):
 if not isinstance(v,tuple):raise TypeError(f"{n} must be a tuple")
 v=tuple(_text(x,f"{n} item") for x in v)
 if len(v)!=len(set(v)):raise ValueError(f"{n} must not contain duplicates")
 return v
def _meta(v):
 if not isinstance(v,Mapping):raise TypeError("metadata must be a mapping")
 try:return MappingProxyType(json.loads(json.dumps(dict(v),sort_keys=True,allow_nan=False)))
 except (TypeError,ValueError) as e:raise ValueError("metadata must be JSON-safe") from e
@dataclass(frozen=True,slots=True)
class MarketBreadthSnapshotV1:
 market_breadth_snapshot_id:str;created_at:datetime;underlying_symbol:str;exchange:str;source_id:str;source_timestamp:datetime
 advance_count:int|None;decline_count:int|None;unchanged_count:int|None;total_count:int|None;covered_count:int;heavyweight_contribution_state:str="UNAVAILABLE";is_partial:bool=False;blockers:tuple[str,...]=();warnings:tuple[str,...]=();metadata:Mapping[str,Any]=field(default_factory=dict);schema_version:str="market_breadth_snapshot.v1"
 def __post_init__(self):
  for n in ("market_breadth_snapshot_id","source_id"):object.__setattr__(self,n,_text(getattr(self,n),n))
  object.__setattr__(self,"created_at",_time(self.created_at,"created_at"));object.__setattr__(self,"source_timestamp",_time(self.source_timestamp,"source_timestamp"))
  identity=normalize_market_identity(self.underlying_symbol,self.exchange)
  if identity is None:raise ValueError("unsupported market identity")
  object.__setattr__(self,"underlying_symbol",identity[0]);object.__setattr__(self,"exchange",identity[1])
  for n in ("advance_count","decline_count","unchanged_count","total_count"):
   v=getattr(self,n)
   if v is not None and (isinstance(v,bool) or not isinstance(v,int)):raise TypeError(f"{n} must be an integer or None")
   if v is not None and v<0:raise ValueError(f"{n} must be non-negative")
  if isinstance(self.covered_count,bool) or not isinstance(self.covered_count,int):raise TypeError("covered_count must be an integer")
  if self.covered_count<0:raise ValueError("covered_count must be non-negative")
  h=_text(self.heavyweight_contribution_state,"heavyweight_contribution_state",True)
  if h not in _H:raise ValueError("unsupported heavyweight_contribution_state")
  object.__setattr__(self,"heavyweight_contribution_state",h)
  if not isinstance(self.is_partial,bool):raise TypeError("is_partial must be a boolean")
  object.__setattr__(self,"blockers",_messages(self.blockers,"blockers"));object.__setattr__(self,"warnings",_messages(self.warnings,"warnings"));object.__setattr__(self,"metadata",_meta(self.metadata))
  if self.schema_version!="market_breadth_snapshot.v1":raise ValueError("unsupported breadth snapshot schema")
 def to_dict(self):
  d={n:getattr(self,n) for n in self.__dataclass_fields__ if n not in {"created_at","source_timestamp","blockers","warnings","metadata"}};d["created_at"]=self.created_at.isoformat();d["source_timestamp"]=self.source_timestamp.isoformat();d["blockers"]=list(self.blockers);d["warnings"]=list(self.warnings);d["metadata"]=dict(self.metadata);return d
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
 def semantic_dict(self):d=self.to_dict();d.pop("market_breadth_snapshot_id");d.pop("created_at");return d
