"""Immutable PAPER-only result shape for future capital/quantity planning."""
from __future__ import annotations
import json,math
from dataclasses import dataclass,field
from datetime import datetime
from types import MappingProxyType
from typing import Any,Mapping
def _t(v,n):
 if type(v)is not str or not(v:=v.strip()):raise ValueError(n)
 return v
def _n(v,n,pos=False,frac=False):
 if type(v)not in (int,float) or isinstance(v,bool) or not math.isfinite(v) or (pos and v<=0) or (not pos and v<0) or (frac and v>1):raise ValueError(n)
 return float(v)
def _freeze(v):
 if v is None or type(v)in(bool,int,str):return v
 if type(v)is float and math.isfinite(v):return v
 if isinstance(v,Mapping):return MappingProxyType(dict(sorted((_t(k,'metadata key'),_freeze(x)) for k,x in v.items())))
 if type(v)in(tuple,list):return tuple(_freeze(x) for x in v)
 raise ValueError('metadata')
def _plain(v):return {k:_plain(v[k]) for k in sorted(v)} if isinstance(v,Mapping) else [_plain(x) for x in v] if isinstance(v,tuple) else v
@dataclass(frozen=True,slots=True)
class CapitalQuantityPlanningResultV1:
 planning_result_id:str;planning_input_id:str;trade_plan_id:str;policy_id:str;option_selection_result_id:str;status:str;available_capital:float|None=None;maximum_capital_utilization_fraction:float|None=None;minimum_reserve_capital:float|None=None;deployable_capital:float|None=None;reserved_capital:float|None=None;risk_model:str|None=None;maximum_risk_fraction:float|None=None;maximum_risk_amount:float|None=None;effective_risk_budget:float|None=None;per_lot_risk_amount:float|None=None;risk_based_lot_limit:int|None=None;estimated_one_lot_premium_cost:float|None=None;upstream_affordable_lot_limit:int|None=None;deployable_capital_affordable_lot_limit:int|None=None;planned_lot_count:int|None=None;lot_size:int|None=None;planned_quantity:int|None=None;estimated_premium_outlay:float|None=None;estimated_risk_amount:float|None=None;target_allocation_enabled:bool=False;target_1_lot_count:int|None=None;target_2_lot_count:int|None=None;target_3_lot_count:int|None=None;runner_lot_count:int|None=None;evaluated_at:datetime|None=None;blockers:tuple[str,...]=();decision_reasons:tuple[str,...]=();warnings:tuple[str,...]=();source_timestamps:Mapping[str,datetime]=field(default_factory=dict);metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str='PAPER';live_execution_eligible:bool=False;schema_version:str='1.0';trading_cost_policy_id:str|None=None;trading_cost_evidence_id:str|None=None;trading_cost_calculation_mode:str|None=None;estimated_brokerage:float|None=None;estimated_exchange_transaction_charges:float|None=None;estimated_clearing_charges:float|None=None;estimated_stt:float|None=None;estimated_sebi_charges:float|None=None;estimated_stamp_duty:float|None=None;estimated_gst:float|None=None;estimated_slippage:float|None=None;estimated_total_trading_cost:float|None=None;estimated_total_capital_requirement:float|None=None;cost_adjusted_capital_feasible:bool|None=None
 def __post_init__(self):
  for n in ('planning_result_id','planning_input_id','trade_plan_id','policy_id','option_selection_result_id'):object.__setattr__(self,n,_t(getattr(self,n),n))
  if self.status not in {'BLOCKED','NO_SIZE','READY'}:raise ValueError('status')
  if not isinstance(self.evaluated_at,datetime) or self.evaluated_at.tzinfo is None:raise ValueError('evaluated_at')
  for n in ('available_capital','maximum_capital_utilization_fraction','minimum_reserve_capital','deployable_capital','reserved_capital','maximum_risk_fraction','maximum_risk_amount','effective_risk_budget','per_lot_risk_amount','estimated_one_lot_premium_cost','estimated_premium_outlay','estimated_risk_amount'):
   v=getattr(self,n)
   if v is not None:object.__setattr__(self,n,_n(v,n,n in {'maximum_capital_utilization_fraction','maximum_risk_fraction','maximum_risk_amount','per_lot_risk_amount','estimated_one_lot_premium_cost'},n in {'maximum_capital_utilization_fraction','maximum_risk_fraction'}))
  for n in ('risk_based_lot_limit','upstream_affordable_lot_limit','deployable_capital_affordable_lot_limit','planned_lot_count','lot_size','planned_quantity','target_1_lot_count','target_2_lot_count','target_3_lot_count','runner_lot_count'):
   v=getattr(self,n)
   if v is not None and (type(v)is not int or isinstance(v,bool) or v<0):raise ValueError(n)
  if self.risk_model is not None and self.risk_model not in {'PREMIUM_AT_RISK','CALLER_SUPPLIED_PER_LOT_RISK'}:raise ValueError('risk_model')
  if type(self.target_allocation_enabled)is not bool:raise TypeError('target_allocation_enabled')
  for n in ('blockers','decision_reasons','warnings'):
   if not isinstance(getattr(self,n),tuple):raise TypeError(n)
   object.__setattr__(self,n,tuple(dict.fromkeys(_t(x,n) for x in getattr(self,n))))
  size=(self.planned_lot_count,self.lot_size,self.planned_quantity,self.estimated_premium_outlay,self.estimated_risk_amount)
  if self.status=='BLOCKED':
   if not self.blockers or self.decision_reasons or any(x is not None for x in size):raise ValueError('BLOCKED')
  elif self.status=='NO_SIZE':
   if self.blockers or not self.decision_reasons or size!=(0,self.lot_size,0,0.,0.) or self.lot_size is None:raise ValueError('NO_SIZE')
  else:
   req=(self.available_capital,self.maximum_capital_utilization_fraction,self.minimum_reserve_capital,self.deployable_capital,self.reserved_capital,self.effective_risk_budget,self.per_lot_risk_amount,self.risk_based_lot_limit,self.estimated_one_lot_premium_cost,self.upstream_affordable_lot_limit,self.deployable_capital_affordable_lot_limit)+size
   if self.blockers or self.decision_reasons or any(x is None for x in req) or self.planned_lot_count<1 or self.lot_size<1 or self.planned_quantity!=self.planned_lot_count*self.lot_size or abs(self.estimated_premium_outlay-self.planned_lot_count*self.estimated_one_lot_premium_cost)>1e-9 or abs(self.estimated_risk_amount-self.planned_lot_count*self.per_lot_risk_amount)>1e-9 or self.planned_lot_count>min(self.risk_based_lot_limit,self.upstream_affordable_lot_limit,self.deployable_capital_affordable_lot_limit):raise ValueError('READY')
  alloc=(self.target_1_lot_count,self.target_2_lot_count,self.target_3_lot_count,self.runner_lot_count)
  if self.target_allocation_enabled:
   if any(x is None for x in alloc) or (self.status=='READY' and sum(alloc)!=self.planned_lot_count) or (self.status=='NO_SIZE' and any(alloc)):raise ValueError('allocation')
  elif any(x not in (None,0) for x in alloc):raise ValueError('allocation')
  if not isinstance(self.source_timestamps,Mapping) or any(type(k)is not str or not k.strip() or not isinstance(v,datetime) or v.tzinfo is None for k,v in self.source_timestamps.items()):raise ValueError('source_timestamps')
  object.__setattr__(self,'source_timestamps',MappingProxyType(dict(sorted(self.source_timestamps.items()))));object.__setattr__(self,'metadata',_freeze(self.metadata))
  if self.execution_mode!='PAPER' or self.live_execution_eligible is not False or self.schema_version!='1.0':raise ValueError('paper')
 def to_dict(self):return {n:(self.evaluated_at.isoformat() if n=='evaluated_at' else {k:v.isoformat() for k,v in self.source_timestamps.items()} if n=='source_timestamps' else _plain(self.metadata) if n=='metadata' else list(getattr(self,n)) if n in {'blockers','decision_reasons','warnings'} else getattr(self,n)) for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False)
 def semantic_dict(self):
  d=self.to_dict()
  for n in ('planning_result_id','evaluated_at','source_timestamps'):d.pop(n)
  return d
