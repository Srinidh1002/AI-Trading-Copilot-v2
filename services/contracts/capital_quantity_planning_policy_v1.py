"""Immutable PAPER-only supplemental policy for future capital planning."""
from __future__ import annotations
import json,math
from dataclasses import dataclass,field
from datetime import datetime
from types import MappingProxyType
from typing import Any,Mapping
def _text(v,n):
 if type(v)is not str or not(v:=v.strip()):raise ValueError(n)
 return v
def _num(v,n,positive=False,fraction=False):
 if type(v)not in (int,float) or isinstance(v,bool) or not math.isfinite(v) or (positive and v<=0) or (not positive and v<0) or (fraction and v>1):raise ValueError(n)
 return float(v)
def _freeze(v):
 if v is None or type(v)in(bool,int,str):return v
 if type(v)is float and math.isfinite(v):return v
 if isinstance(v,Mapping):return MappingProxyType(dict(sorted((_text(k,'metadata key'),_freeze(x)) for k,x in v.items())))
 if type(v)in(tuple,list):return tuple(_freeze(x) for x in v)
 raise ValueError('metadata')
def _plain(v):return {k:_plain(v[k]) for k in sorted(v)} if isinstance(v,Mapping) else [_plain(x) for x in v] if isinstance(v,tuple) else v
@dataclass(frozen=True,slots=True)
class CapitalQuantityPlanningPolicyV1:
 policy_id:str;maximum_capital_utilization_fraction:float;minimum_reserve_capital:float=0.;risk_model:str='PREMIUM_AT_RISK';maximum_risk_fraction:float|None=None;maximum_risk_amount:float|None=None;minimum_planned_lot_count:int=1;maximum_planned_lot_count:int=1;target_allocation_enabled:bool=False;target_allocation_weights:tuple[float,...]=();policy_timestamp:datetime|None=None;policy_source:str='CALLER';warnings:tuple[str,...]=();source_timestamps:Mapping[str,datetime]=field(default_factory=dict);metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str='PAPER';live_execution_eligible:bool=False;schema_version:str='1.0'
 def __post_init__(self):
  object.__setattr__(self,'policy_id',_text(self.policy_id,'policy_id'));object.__setattr__(self,'maximum_capital_utilization_fraction',_num(self.maximum_capital_utilization_fraction,'utilization',True,True));object.__setattr__(self,'minimum_reserve_capital',_num(self.minimum_reserve_capital,'reserve'))
  if self.risk_model not in {'PREMIUM_AT_RISK','CALLER_SUPPLIED_PER_LOT_RISK'}:raise ValueError('risk_model')
  for n in ('maximum_risk_fraction','maximum_risk_amount'):
   v=getattr(self,n)
   if v is not None:object.__setattr__(self,n,_num(v,n,True,n=='maximum_risk_fraction'))
  if self.maximum_risk_fraction is None and self.maximum_risk_amount is None:raise ValueError('risk limit')
  for n in ('minimum_planned_lot_count','maximum_planned_lot_count'):
   v=getattr(self,n)
   if type(v)is not int or isinstance(v,bool) or v<1:raise ValueError(n)
  if self.maximum_planned_lot_count<self.minimum_planned_lot_count:raise ValueError('lot bounds')
  if type(self.target_allocation_enabled)is not bool or not isinstance(self.target_allocation_weights,tuple):raise TypeError('target allocation')
  w=tuple(_num(x,'target weight') for x in self.target_allocation_weights)
  if (self.target_allocation_enabled and (len(w)!=3 or not sum(w)>0)) or (not self.target_allocation_enabled and w):raise ValueError('target allocation')
  object.__setattr__(self,'target_allocation_weights',w)
  if not isinstance(self.policy_timestamp,datetime) or self.policy_timestamp.tzinfo is None:raise ValueError('policy_timestamp')
  object.__setattr__(self,'policy_source',_text(self.policy_source,'policy_source'))
  if not isinstance(self.warnings,tuple):raise TypeError('warnings')
  object.__setattr__(self,'warnings',tuple(dict.fromkeys(_text(x,'warning') for x in self.warnings)))
  if not isinstance(self.source_timestamps,Mapping) or any(type(k)is not str or not k.strip() or not isinstance(v,datetime) or v.tzinfo is None for k,v in self.source_timestamps.items()):raise ValueError('source_timestamps')
  object.__setattr__(self,'source_timestamps',MappingProxyType(dict(sorted(self.source_timestamps.items()))));object.__setattr__(self,'metadata',_freeze(self.metadata))
  if self.execution_mode!='PAPER' or self.live_execution_eligible is not False or self.schema_version!='1.0':raise ValueError('paper')
 @property
 def target_remainder_priority(self):return ('T1','T2','T3')
 def to_dict(self):return {n:(self.policy_timestamp.isoformat() if n=='policy_timestamp' else {k:v.isoformat() for k,v in self.source_timestamps.items()} if n=='source_timestamps' else _plain(self.metadata) if n=='metadata' else list(getattr(self,n)) if n in {'warnings','target_allocation_weights'} else getattr(self,n)) for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False)
 def semantic_dict(self):
  d=self.to_dict()
  for n in ('policy_id','policy_timestamp','source_timestamps'):d.pop(n)
  return d
