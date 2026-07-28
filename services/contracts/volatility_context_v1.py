"""Immutable supplied India-VIX context; no provider interpretation."""
from __future__ import annotations
import json,math
from dataclasses import dataclass,field
from datetime import datetime
from types import MappingProxyType
from typing import Any,Mapping
from services.core.market_identity import normalize_market_identity
_R={"LOW","NORMAL","ELEVATED","HIGH","EXTREME","UNAVAILABLE"}; _D={"RISING","FALLING","STABLE","UNAVAILABLE"}; _S={"READY","READY_WITH_WARNINGS","STALE","UNAVAILABLE","BLOCKED"}; _X=_S-{"READY","READY_WITH_WARNINGS"}
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
def _metadata(v):
 if not isinstance(v,Mapping):raise TypeError("metadata must be a mapping")
 try:return MappingProxyType(json.loads(json.dumps(dict(v),sort_keys=True,allow_nan=False)))
 except (TypeError,ValueError) as e:raise ValueError("metadata must be JSON-safe") from e
@dataclass(frozen=True,slots=True)
class VolatilityContextV1:
 volatility_context_id:str; created_at:datetime; underlying_symbol:str; exchange:str; volatility_symbol:str; volatility_exchange:str; source_id:str; source_timestamp:datetime
 volatility_value:float|None; volatility_change_percent:float|None; volatility_regime:str; volatility_direction:str; volatility_strength:float; context_status:str
 blockers:tuple[str,...]=();warnings:tuple[str,...]=();metadata:Mapping[str,Any]=field(default_factory=dict)
 execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="volatility_context.v1"
 def __post_init__(self):
  for n in ("volatility_context_id","source_id"):object.__setattr__(self,n,_text(getattr(self,n),n))
  object.__setattr__(self,"created_at",_time(self.created_at,"created_at"));object.__setattr__(self,"source_timestamp",_time(self.source_timestamp,"source_timestamp"))
  identity=normalize_market_identity(self.underlying_symbol,self.exchange)
  if identity is None:raise ValueError("unsupported market identity")
  object.__setattr__(self,"underlying_symbol",identity[0]);object.__setattr__(self,"exchange",identity[1])
  if _text(self.volatility_symbol,"volatility_symbol",True)!="INDIA_VIX" or _text(self.volatility_exchange,"volatility_exchange",True)!="NSE":raise ValueError("volatility identity must be INDIA_VIX/NSE")
  object.__setattr__(self,"volatility_symbol","INDIA_VIX");object.__setattr__(self,"volatility_exchange","NSE")
  for n,a in (("volatility_regime",_R),("volatility_direction",_D),("context_status",_S)):
   v=_text(getattr(self,n),n,True)
   if v not in a:raise ValueError(f"unsupported {n}")
   object.__setattr__(self,n,v)
  for n,positive in (("volatility_value",True),("volatility_change_percent",False)):
   v=getattr(self,n)
   if v is not None:
    if isinstance(v,bool) or not isinstance(v,(int,float)):raise TypeError(f"{n} must be numeric or None")
    v=float(v)
    if not math.isfinite(v) or (positive and v<0):raise ValueError(f"{n} must be finite and non-negative" if positive else f"{n} must be finite")
   object.__setattr__(self,n,v)
  v=self.volatility_strength
  if isinstance(v,bool) or not isinstance(v,(int,float)):raise TypeError("volatility_strength must be numeric")
  v=float(v)
  if not math.isfinite(v) or not 0<=v<=1:raise ValueError("volatility_strength must be between zero and one")
  object.__setattr__(self,"volatility_strength",v);object.__setattr__(self,"blockers",_messages(self.blockers,"blockers"));object.__setattr__(self,"warnings",_messages(self.warnings,"warnings"));object.__setattr__(self,"metadata",_metadata(self.metadata))
  if self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="volatility_context.v1":raise ValueError("volatility context is paper-only v1")
  if self.context_status=="READY" and (self.blockers or self.warnings or self.volatility_value is None or self.volatility_regime=="UNAVAILABLE" or self.volatility_direction=="UNAVAILABLE"):raise ValueError("READY volatility context is contradictory")
  if self.context_status=="READY_WITH_WARNINGS" and (self.blockers or not self.warnings or self.volatility_value is None or self.volatility_regime=="UNAVAILABLE" or self.volatility_direction=="UNAVAILABLE"):raise ValueError("READY_WITH_WARNINGS volatility context is contradictory")
  if self.context_status in _X and (not self.blockers or self.volatility_value is not None or self.volatility_change_percent is not None or self.volatility_regime!="UNAVAILABLE" or self.volatility_direction!="UNAVAILABLE" or self.volatility_strength!=0):raise ValueError("unavailable volatility context must be explicit and blocked")
 def to_dict(self):
  d={n:getattr(self,n) for n in self.__dataclass_fields__ if n not in {"created_at","source_timestamp","blockers","warnings","metadata"}};d["created_at"]=self.created_at.isoformat();d["source_timestamp"]=self.source_timestamp.isoformat();d["blockers"]=list(self.blockers);d["warnings"]=list(self.warnings);d["metadata"]=dict(self.metadata);return d
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
 def semantic_dict(self):d=self.to_dict();d.pop("volatility_context_id");d.pop("created_at");return d
