"""Immutable normalized INDIA_VIX input; regimes are adapter supplied."""
from __future__ import annotations
import json,math
from dataclasses import dataclass,field
from datetime import datetime
from types import MappingProxyType
from typing import Any,Mapping
from services.core.market_identity import normalize_market_identity
_R={"LOW","NORMAL","ELEVATED","HIGH","EXTREME","UNAVAILABLE"}
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
class VolatilitySnapshotV1:
 volatility_snapshot_id:str;created_at:datetime;underlying_symbol:str;exchange:str;volatility_symbol:str;volatility_exchange:str;source_id:str;source_timestamp:datetime;volatility_value:float|None;previous_volatility_value:float|None;volatility_change_percent:float|None;normalized_volatility_regime:str;is_partial:bool=False;blockers:tuple[str,...]=();warnings:tuple[str,...]=();metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="volatility_snapshot.v1"
 def __post_init__(self):
  for n in ("volatility_snapshot_id","source_id"):object.__setattr__(self,n,_text(getattr(self,n),n))
  object.__setattr__(self,"created_at",_time(self.created_at,"created_at"));object.__setattr__(self,"source_timestamp",_time(self.source_timestamp,"source_timestamp"))
  identity=normalize_market_identity(self.underlying_symbol,self.exchange)
  if identity is None:raise ValueError("unsupported market identity")
  object.__setattr__(self,"underlying_symbol",identity[0]);object.__setattr__(self,"exchange",identity[1])
  if _text(self.volatility_symbol,"volatility_symbol",True)!="INDIA_VIX" or _text(self.volatility_exchange,"volatility_exchange",True)!="NSE":raise ValueError("volatility identity must be INDIA_VIX/NSE")
  object.__setattr__(self,"volatility_symbol","INDIA_VIX");object.__setattr__(self,"volatility_exchange","NSE")
  for n in ("volatility_value","previous_volatility_value","volatility_change_percent"):
   v=getattr(self,n)
   if v is not None:
    if isinstance(v,bool) or not isinstance(v,(int,float)):raise TypeError(f"{n} must be numeric or None")
    v=float(v)
    if not math.isfinite(v) or (n!="volatility_change_percent" and v<0):raise ValueError(f"{n} must be finite and non-negative" if n!="volatility_change_percent" else f"{n} must be finite")
   object.__setattr__(self,n,v)
  regime=_text(self.normalized_volatility_regime,"normalized_volatility_regime",True)
  if regime not in _R:raise ValueError("unsupported normalized_volatility_regime")
  if self.volatility_value is None and regime!="UNAVAILABLE":raise ValueError("missing volatility value requires UNAVAILABLE regime")
  if regime!="UNAVAILABLE" and (self.volatility_value is None or self.volatility_value<=0):raise ValueError("available normalized regime requires positive volatility value")
  if regime=="UNAVAILABLE" and self.volatility_value is not None and not (self.blockers or self.warnings):raise ValueError("unavailable regime with value requires explanation")
  if self.volatility_value is not None and self.previous_volatility_value is not None:
   if self.previous_volatility_value==0:raise ValueError("zero previous volatility cannot support a change")
   expected=(self.volatility_value-self.previous_volatility_value)/self.previous_volatility_value*100
   if self.volatility_change_percent is not None and not math.isclose(self.volatility_change_percent,expected,rel_tol=0.,abs_tol=1e-9):raise ValueError("volatility_change_percent is inconsistent with values")
   if self.volatility_change_percent is None:object.__setattr__(self,"volatility_change_percent",expected)
  object.__setattr__(self,"normalized_volatility_regime",regime)
  if not isinstance(self.is_partial,bool):raise TypeError("is_partial must be a boolean")
  object.__setattr__(self,"blockers",_msgs(self.blockers,"blockers"));object.__setattr__(self,"warnings",_msgs(self.warnings,"warnings"));object.__setattr__(self,"metadata",_meta(self.metadata))
  if self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="volatility_snapshot.v1":raise ValueError("volatility snapshot is paper-only v1")
 def to_dict(self):
  d={n:getattr(self,n) for n in self.__dataclass_fields__ if n not in {"created_at","source_timestamp","blockers","warnings","metadata"}};d["created_at"]=self.created_at.isoformat();d["source_timestamp"]=self.source_timestamp.isoformat();d["blockers"]=list(self.blockers);d["warnings"]=list(self.warnings);d["metadata"]=dict(self.metadata);return d
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
 def semantic_dict(self):d=self.to_dict();d.pop("volatility_snapshot_id");d.pop("created_at");return d
