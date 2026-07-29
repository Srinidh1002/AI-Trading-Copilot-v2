from __future__ import annotations
import json, math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping
from .paper_market_observation_v1 import _freeze_json_value,_plain_json_value
from .paper_market_observation_v1 import PaperMarketObservationV1,_aware_datetime,_nonblank_text
from .paper_trade_position_v1 import PaperTradePositionV1
from .paper_trade_lifecycle_policy_v1 import PaperTradeLifecyclePolicyV1
from .paper_trade_lifecycle_state_v1 import PaperTradeLifecycleStateV1
@dataclass(frozen=True,slots=True)
class PaperTradePositionEvaluationInputV1:
 position:PaperTradePositionV1;lifecycle_policy:PaperTradeLifecyclePolicyV1;lifecycle_state:PaperTradeLifecycleStateV1;observation:PaperMarketObservationV1;evaluation_timestamp:datetime;requested_transition_id:str;resulting_lifecycle_state_id:str;evaluation_result_id:str;exit_fill_ids:tuple[str,...];pnl_evidence_id:str;target_1_exit_cost:float=0.;target_2_exit_cost:float=0.;target_3_exit_cost:float=0.;stop_exit_cost:float=0.;session_exit_cost:float=0.;expiry_exit_cost:float=0.;invalidation_exit_cost:float=0.;runner_exit_cost:float=0.;cancellation_exit_cost:float=0.;invalidation_status:str='ABSENT';invalidation_reason_code:str|None=None;cancellation_status:str='ABSENT';cancellation_reason_code:str|None=None;metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str='PAPER';live_execution_eligible:bool=False;schema_version:str='1.0'
 def __post_init__(self):
  if type(self.position)is not PaperTradePositionV1 or type(self.lifecycle_policy)is not PaperTradeLifecyclePolicyV1 or type(self.lifecycle_state)is not PaperTradeLifecycleStateV1 or type(self.observation)is not PaperMarketObservationV1:raise TypeError('contracts')
  if self.position.lifecycle_state not in {'OPEN','PARTIALLY_EXITED'} or self.lifecycle_state.current_state!=self.position.lifecycle_state:raise ValueError('state')
  if (self.position.trade_plan_id,self.position.integrated_trade_plan_result_id,self.position.lifecycle_policy_id)!=(self.lifecycle_state.trade_plan_id,self.lifecycle_state.integrated_trade_plan_result_id,self.lifecycle_policy.lifecycle_policy_id):raise ValueError('identity')
  if (self.observation.trade_plan_id,self.observation.integrated_trade_plan_result_id,self.observation.selected_option_contract_id,self.observation.option_symbol)!=(self.position.trade_plan_id,self.position.integrated_trade_plan_result_id,self.position.selected_option_contract_id,self.position.option_symbol):raise ValueError('observation')
  object.__setattr__(self,'evaluation_timestamp',_aware_datetime(self.evaluation_timestamp,'evaluation_timestamp'))
  for n in ('requested_transition_id','resulting_lifecycle_state_id','evaluation_result_id','pnl_evidence_id'):object.__setattr__(self,n,_nonblank_text(getattr(self,n),n))
  if type(self.exit_fill_ids)is not tuple or not self.exit_fill_ids or len(set(self.exit_fill_ids))!=len(self.exit_fill_ids):raise ValueError('exit_fill_ids')
  for x in self.exit_fill_ids:_nonblank_text(x,'exit_fill_id')
  used={self.position.entry_fill.fill_id,*[fill.fill_id for fill in self.position.exit_fills]}
  if used.intersection(self.exit_fill_ids):raise ValueError('exit_fill_ids already used')
  for n in ('target_1_exit_cost','target_2_exit_cost','target_3_exit_cost','stop_exit_cost','session_exit_cost','expiry_exit_cost','invalidation_exit_cost','runner_exit_cost','cancellation_exit_cost'):
   v=getattr(self,n)
   if type(v)not in (int,float) or isinstance(v,bool) or not math.isfinite(v) or v<0:raise ValueError(n)
  if type(self.invalidation_status)is not str or self.invalidation_status not in {'ABSENT','NOT_TRIGGERED','TRIGGERED'}:raise ValueError('invalidation_status')
  if self.invalidation_status=='TRIGGERED':
   if type(self.invalidation_reason_code)is not str or not self.invalidation_reason_code.strip():raise ValueError('invalidation_reason_code')
   object.__setattr__(self,'invalidation_reason_code',self.invalidation_reason_code.strip())
  elif self.invalidation_reason_code is not None:raise ValueError('invalidation_reason_code')
  if type(self.cancellation_status)is not str or self.cancellation_status not in {'ABSENT','NOT_REQUESTED','REQUESTED'}:raise ValueError('cancellation_status')
  if self.cancellation_status=='REQUESTED':
   if type(self.cancellation_reason_code)is not str or not self.cancellation_reason_code.strip():raise ValueError('cancellation_reason_code')
   object.__setattr__(self,'cancellation_reason_code',self.cancellation_reason_code.strip())
  elif self.cancellation_reason_code is not None:raise ValueError('cancellation_reason_code')
  object.__setattr__(self,'metadata',_freeze_json_value(self.metadata))
  if self.execution_mode!='PAPER'or self.live_execution_eligible is not False or self.schema_version!='1.0':raise ValueError('paper')
 def to_dict(self):
  nested={'position':self.position,'lifecycle_policy':self.lifecycle_policy,'lifecycle_state':self.lifecycle_state,'observation':self.observation}
  return {n:(self.evaluation_timestamp.isoformat()if n=='evaluation_timestamp'else _plain_json_value(self.metadata)if n=='metadata'else nested[n].to_dict()if n in nested else getattr(self,n))for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False)
 def semantic_dict(self):
  d=self.to_dict();d.pop('evaluation_result_id');return d
