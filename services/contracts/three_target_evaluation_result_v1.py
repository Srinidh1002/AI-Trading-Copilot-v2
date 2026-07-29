from __future__ import annotations
import json
from dataclasses import dataclass,field
from datetime import datetime
from typing import Any,Mapping
from .stop_loss_evaluation_input_v1 import _PAIR,_text,_aware,_diag,_stamps,_freeze,_plain
from .trade_plan_target_v1 import TradePlanTargetV1
@dataclass(frozen=True,slots=True)
class ThreeTargetEvaluationResultV1:
 evaluation_result_id:str;evaluation_id:str;evaluated_at:datetime;underlying_symbol:str;exchange:str;direction:str;option_right:str;target_method:str;selected_target_source:str|None;status:str;target_1:TradePlanTargetV1|None;target_2:TradePlanTargetV1|None;target_3:TradePlanTargetV1|None;entry_reference_price:float;stop_loss_price:float;stop_distance:float;stop_distance_fraction:float;minimum_reward_to_risk_t1:float;minimum_reward_to_risk_t2:float;minimum_reward_to_risk_t3:float;target_1_multiplier:float;target_2_multiplier:float;target_3_multiplier:float;blockers:tuple[str,...]=();warnings:tuple[str,...]=();decision_reasons:tuple[str,...]=();source_timestamps:Mapping[str,datetime]=field(default_factory=dict);metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str='PAPER';live_execution_eligible:bool=False;schema_version:str='1.0'
 def __post_init__(self):
  for n in ('evaluation_result_id','evaluation_id'):object.__setattr__(self,n,_text(getattr(self,n),n))
  object.__setattr__(self,'evaluated_at',_aware(self.evaluated_at,'evaluated_at'))
  if self.direction not in _PAIR or self.option_right!=_PAIR[self.direction] or self.target_method not in {'RISK_MULTIPLE','ATR','EXPECTED_MOVE','STRUCTURE','HYBRID'} or self.status not in {'READY','BLOCKED','NO_TARGETS'}:raise ValueError('vocabulary')
  ts=(self.target_1,self.target_2,self.target_3)
  if any(x is not None for x in ts) and any(x is None for x in ts):raise ValueError('partial targets')
  for n in ('blockers','warnings','decision_reasons'):object.__setattr__(self,n,_diag(getattr(self,n),n))
  if self.status=='READY':
   if self.blockers or any(type(x)is not TradePlanTargetV1 for x in ts) or [x.target_number for x in ts]!=[1,2,3] or not ts[0].target_price<ts[1].target_price<ts[2].target_price or abs(sum(x.allocation_fraction for x in ts)-1)>1e-9:raise ValueError('READY')
  if self.status=='BLOCKED' and not self.blockers:raise ValueError('BLOCKED')
  if self.status=='NO_TARGETS' and not self.decision_reasons:raise ValueError('NO_TARGETS')
  object.__setattr__(self,'source_timestamps',_stamps(self.source_timestamps));object.__setattr__(self,'metadata',_freeze(self.metadata))
  if self.execution_mode!='PAPER' or self.live_execution_eligible is not False:raise ValueError('paper')
 @property
 def weighted_reward_to_risk(self):return None if self.target_1 is None else sum(x.reward_to_risk*x.allocation_fraction for x in (self.target_1,self.target_2,self.target_3))
 def to_dict(self):return {n:(self.evaluated_at.isoformat() if n=='evaluated_at' else {k:v.isoformat() for k,v in self.source_timestamps.items()} if n=='source_timestamps' else _plain(self.metadata) if n=='metadata' else list(getattr(self,n)) if n in {'blockers','warnings','decision_reasons'} else getattr(self,n).to_dict() if n in {'target_1','target_2','target_3'} and getattr(self,n) else getattr(self,n)) for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False)
 def semantic_dict(self):
  d=self.to_dict()
  for n in ('evaluation_result_id','evaluation_id','evaluated_at','source_timestamps'):d.pop(n)
  return d
