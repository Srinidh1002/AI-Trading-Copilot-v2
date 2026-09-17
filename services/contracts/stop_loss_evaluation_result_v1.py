"""Immutable PAPER-only result of deterministic stop-loss evaluation."""
from __future__ import annotations
import json, math
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping
from services.core.market_identity import normalize_market_identity
from .stop_loss_evaluation_input_v1 import _PAIR,_text,_aware,_positive,_diag,_stamps,_freeze,_plain

@dataclass(frozen=True,slots=True)
class StopLossEvaluationResultV1:
 evaluation_result_id:str; evaluation_id:str; evaluated_at:datetime; underlying_symbol:str; exchange:str; direction:str; option_right:str
 stop_method:str; selected_stop_source:str|None; status:str; stop_loss_price:float|None; stop_reference_price:float|None; stop_distance:float|None; stop_distance_fraction:float|None; minimum_stop_distance_fraction:float|None; maximum_stop_distance_fraction:float|None
 blockers:tuple[str,...]=(); warnings:tuple[str,...]=(); decision_reasons:tuple[str,...]=(); invalidation_rules:tuple[str,...]=(); source_timestamps:Mapping[str,datetime]=field(default_factory=dict); metadata:Mapping[str,Any]=field(default_factory=dict)
 execution_mode:str="PAPER"; live_execution_eligible:bool=False; schema_version:str="1.0"
 def __post_init__(self):
  for n in ("evaluation_result_id","evaluation_id"):object.__setattr__(self,n,_text(getattr(self,n),n))
  object.__setattr__(self,"evaluated_at",_aware(self.evaluated_at,"evaluated_at"))
  identity=normalize_market_identity(self.underlying_symbol,self.exchange)
  if identity is None:raise ValueError("unsupported canonical identity")
  object.__setattr__(self,"underlying_symbol",identity[0]);object.__setattr__(self,"exchange",identity[1])
  if self.direction not in _PAIR or self.option_right!=_PAIR[self.direction]:raise ValueError("direction and option_right must agree")
  if self.stop_method not in {"ATR","STRUCTURE","PREMIUM_FRACTION","HYBRID"}:raise ValueError("unsupported stop method")
  if self.selected_stop_source is not None and self.selected_stop_source not in {"ATR","STRUCTURE_STOP","RECENT_SWING_LOW","PREMIUM_FRACTION"}:raise ValueError("unsupported stop source")
  if self.status not in {"READY","BLOCKED","NO_STOP"}:raise ValueError("unsupported status")
  for n in ("stop_loss_price","stop_reference_price","stop_distance"):object.__setattr__(self,n,_positive(getattr(self,n),n,True))
  for n in ("stop_distance_fraction","minimum_stop_distance_fraction","maximum_stop_distance_fraction"):
   v=getattr(self,n)
   if v is not None and (type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1):raise ValueError(f"{n} must be a fraction")
   object.__setattr__(self,n,None if v is None else float(v))
  group=(self.selected_stop_source,self.stop_loss_price,self.stop_reference_price,self.stop_distance,self.stop_distance_fraction,self.minimum_stop_distance_fraction,self.maximum_stop_distance_fraction)
  if any(x is not None for x in group) and any(x is None for x in group):raise ValueError("stop geometry must be wholly present or absent")
  if all(x is not None for x in group):
   if not self.stop_loss_price<self.stop_reference_price or abs(self.stop_distance-(self.stop_reference_price-self.stop_loss_price))>1e-9 or abs(self.stop_distance_fraction-self.stop_distance/self.stop_reference_price)>1e-9 or self.minimum_stop_distance_fraction>self.maximum_stop_distance_fraction:raise ValueError("invalid stop geometry")
  for n in ("blockers","warnings","decision_reasons","invalidation_rules"):object.__setattr__(self,n,_diag(getattr(self,n),n))
  if self.status=="READY" and (any(x is None for x in group) or self.blockers or not self.invalidation_rules):raise ValueError("READY requires complete geometry, rules, and no blockers")
  if self.status=="BLOCKED" and not self.blockers:raise ValueError("BLOCKED requires blockers")
  if self.status=="NO_STOP" and not self.decision_reasons:raise ValueError("NO_STOP requires reasons")
  object.__setattr__(self,"source_timestamps",_stamps(self.source_timestamps));object.__setattr__(self,"metadata",_freeze(self.metadata))
  if self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="1.0":raise ValueError("PAPER-only schema required")
 @property
 def risk_per_unit(self):return self.stop_distance
 @property
 def distance_from_entry_fraction(self):return self.stop_distance_fraction
 def to_dict(self):
  return {n:(self.evaluated_at.isoformat() if n=="evaluated_at" else {k:v.isoformat() for k,v in self.source_timestamps.items()} if n=="source_timestamps" else _plain(self.metadata) if n=="metadata" else list(getattr(self,n)) if n in {"blockers","warnings","decision_reasons","invalidation_rules"} else getattr(self,n)) for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
 def semantic_dict(self):
  d=self.to_dict()
  for n in ("evaluation_result_id","evaluation_id","evaluated_at","source_timestamps"):d.pop(n)
  return d
