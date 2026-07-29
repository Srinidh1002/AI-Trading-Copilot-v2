from __future__ import annotations
import json,math
from dataclasses import dataclass,field
from datetime import datetime
from typing import Any,Mapping
from .stop_loss_evaluation_input_v1 import _PAIR,_text,_aware,_positive,_diag,_stamps,_freeze,_plain
@dataclass(frozen=True,slots=True)
class ThreeTargetEvaluationInputV1:
 evaluation_id:str;evaluation_result_id:str;evaluated_at:datetime;trade_plan_input_id:str;policy_id:str;entry_evaluation_result_id:str;stop_evaluation_result_id:str;underlying_symbol:str;exchange:str;direction:str;option_right:str;entry_reference_price:float;stop_loss_price:float;stop_distance:float;stop_distance_fraction:float;atr_value:float|None;expected_move_value:float|None;structure_target_1:float|None;structure_target_2:float|None;structure_target_3:float|None;resistance_levels:tuple[float,...]=();support_levels:tuple[float,...]=();planning_allowed:bool=True;blockers:tuple[str,...]=();warnings:tuple[str,...]=();source_timestamps:Mapping[str,datetime]=field(default_factory=dict);metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str='PAPER';live_execution_eligible:bool=False;schema_version:str='1.0'
 def __post_init__(self):
  for n in ('evaluation_id','evaluation_result_id','trade_plan_input_id','policy_id','entry_evaluation_result_id','stop_evaluation_result_id'):object.__setattr__(self,n,_text(getattr(self,n),n))
  object.__setattr__(self,'evaluated_at',_aware(self.evaluated_at,'evaluated_at'))
  from services.core.market_identity import normalize_market_identity
  i=normalize_market_identity(self.underlying_symbol,self.exchange)
  if i is None or self.direction not in _PAIR or self.option_right!=_PAIR[self.direction]:raise ValueError('identity')
  object.__setattr__(self,'underlying_symbol',i[0]);object.__setattr__(self,'exchange',i[1])
  for n in ('entry_reference_price','stop_loss_price','stop_distance'):object.__setattr__(self,n,_positive(getattr(self,n),n))
  if not self.stop_loss_price<self.entry_reference_price or abs(self.stop_distance-(self.entry_reference_price-self.stop_loss_price))>1e-9 or abs(self.stop_distance_fraction-self.stop_distance/self.entry_reference_price)>1e-9:raise ValueError('stop geometry')
  object.__setattr__(self,'stop_distance_fraction',float(self.stop_distance_fraction))
  for n in ('atr_value','expected_move_value','structure_target_1','structure_target_2','structure_target_3'):object.__setattr__(self,n,_positive(getattr(self,n),n,True))
  for n in ('resistance_levels','support_levels'):
   v=tuple(_positive(x,n) for x in getattr(self,n))
   if len(set(v))!=len(v):raise ValueError(n)
   object.__setattr__(self,n,v)
  if type(self.planning_allowed)is not bool:raise TypeError('planning_allowed')
  for n in ('blockers','warnings'):object.__setattr__(self,n,_diag(getattr(self,n),n))
  object.__setattr__(self,'source_timestamps',_stamps(self.source_timestamps));object.__setattr__(self,'metadata',_freeze(self.metadata))
  if self.execution_mode!='PAPER' or self.live_execution_eligible is not False or self.schema_version!='1.0':raise ValueError('paper')
 def to_dict(self):return {n:(self.evaluated_at.isoformat() if n=='evaluated_at' else {k:v.isoformat() for k,v in self.source_timestamps.items()} if n=='source_timestamps' else _plain(self.metadata) if n=='metadata' else list(getattr(self,n)) if n in {'resistance_levels','support_levels','blockers','warnings'} else getattr(self,n)) for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False)
 def semantic_dict(self):
  d=self.to_dict()
  for n in ('evaluation_id','evaluation_result_id','evaluated_at','source_timestamps'):d.pop(n)
  return d
