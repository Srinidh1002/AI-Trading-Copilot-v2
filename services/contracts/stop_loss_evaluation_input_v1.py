"""Immutable PAPER-only supplied evidence for stop-loss evaluation."""
from __future__ import annotations
import json, math
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping
from services.core.market_identity import normalize_market_identity

_PAIR={"BULLISH":"CALL","BEARISH":"PUT"}
def _text(v,n):
 if type(v)is not str or not v.strip(): raise ValueError(f"{n} must be nonblank")
 return v
def _aware(v,n):
 if not isinstance(v,datetime) or v.tzinfo is None or v.utcoffset() is None: raise ValueError(f"{n} must be aware")
 return v
def _positive(v,n,optional=False):
 if v is None and optional:return None
 if type(v) not in (int,float) or not math.isfinite(v) or v<=0:raise ValueError(f"{n} must be positive")
 return float(v)
def _diag(v,n):
 if not isinstance(v,tuple):raise TypeError(f"{n} must be a tuple")
 out=[]
 for x in v:
  if type(x)is not str or not (x:=x.strip()):raise ValueError(f"{n} entries must be nonblank strings")
  if x not in out:out.append(x)
 return tuple(out)
def _stamps(v):
 if not isinstance(v,Mapping):raise TypeError("source_timestamps must be a mapping")
 return MappingProxyType(dict(sorted(((_text(k,"source timestamp key"),_aware(x,"source timestamp")) for k,x in v.items()))))
def _freeze(v):
 if v is None or type(v) in (bool,int,str):return v
 if type(v)is float:
  if not math.isfinite(v):raise ValueError("metadata must be JSON-safe")
  return v
 if isinstance(v,Mapping):return MappingProxyType(dict(sorted((_text(k,"metadata key"),_freeze(x)) for k,x in v.items())))
 if type(v) in (list,tuple):return tuple(_freeze(x) for x in v)
 raise ValueError("metadata must be JSON-safe")
def _plain(v):
 if isinstance(v,Mapping):return {k:_plain(v[k]) for k in sorted(v)}
 if isinstance(v,tuple):return [_plain(x) for x in v]
 return v

@dataclass(frozen=True,slots=True)
class StopLossEvaluationInputV1:
 evaluation_id:str; evaluation_result_id:str; evaluated_at:datetime; trade_plan_input_id:str; policy_id:str; entry_evaluation_result_id:str
 underlying_symbol:str; exchange:str; direction:str; option_right:str
 entry_reference_price:float; entry_zone_lower:float; entry_zone_upper:float
 atr_value:float|None; structure_stop_price:float|None; premium_reference_price:float|None; recent_swing_low:float|None; recent_swing_high:float|None
 planning_allowed:bool; blockers:tuple[str,...]=(); warnings:tuple[str,...]=(); source_timestamps:Mapping[str,datetime]=field(default_factory=dict); metadata:Mapping[str,Any]=field(default_factory=dict)
 execution_mode:str="PAPER"; live_execution_eligible:bool=False; schema_version:str="1.0"
 def __post_init__(self):
  for n in ("evaluation_id","evaluation_result_id","trade_plan_input_id","policy_id","entry_evaluation_result_id"):object.__setattr__(self,n,_text(getattr(self,n),n))
  object.__setattr__(self,"evaluated_at",_aware(self.evaluated_at,"evaluated_at"))
  identity=normalize_market_identity(self.underlying_symbol,self.exchange)
  if identity is None:raise ValueError("unsupported canonical identity")
  object.__setattr__(self,"underlying_symbol",identity[0]);object.__setattr__(self,"exchange",identity[1])
  if self.direction not in _PAIR or self.option_right!=_PAIR[self.direction]:raise ValueError("direction and option_right must agree")
  for n in ("entry_reference_price","entry_zone_lower","entry_zone_upper"):object.__setattr__(self,n,_positive(getattr(self,n),n))
  if not self.entry_zone_lower<self.entry_zone_upper or not self.entry_zone_lower<=self.entry_reference_price<=self.entry_zone_upper:raise ValueError("entry geometry is incoherent")
  for n in ("atr_value","structure_stop_price","premium_reference_price","recent_swing_low","recent_swing_high"):object.__setattr__(self,n,_positive(getattr(self,n),n,True))
  if type(self.planning_allowed)is not bool:raise TypeError("planning_allowed must be bool")
  object.__setattr__(self,"blockers",_diag(self.blockers,"blockers"));object.__setattr__(self,"warnings",_diag(self.warnings,"warnings"));object.__setattr__(self,"source_timestamps",_stamps(self.source_timestamps));object.__setattr__(self,"metadata",_freeze(self.metadata))
  if self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="1.0":raise ValueError("PAPER-only schema required")
 def to_dict(self):
  return {n:(self.evaluated_at.isoformat() if n=="evaluated_at" else {k:v.isoformat() for k,v in self.source_timestamps.items()} if n=="source_timestamps" else _plain(self.metadata) if n=="metadata" else list(getattr(self,n)) if n in {"blockers","warnings"} else getattr(self,n)) for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
 def semantic_dict(self):
  d=self.to_dict()
  for n in ("evaluation_id","evaluation_result_id","evaluated_at","source_timestamps"):d.pop(n)
  return d
