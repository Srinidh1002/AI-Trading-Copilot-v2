from __future__ import annotations
import json
from dataclasses import dataclass,field
from typing import Any,Mapping
from .paper_trade_position_v1 import PaperTradePositionV1
from .paper_trade_fill_v1 import PaperTradeFillV1
from .paper_trade_pnl_evidence_v1 import PaperTradePnlEvidenceV1
from .paper_trade_lifecycle_state_v1 import PaperTradeLifecycleStateV1
from .paper_market_observation_v1 import _freeze_json_value,_freeze_warnings,_nonblank_text,_plain_json_value
@dataclass(frozen=True,slots=True)
class PaperTradePositionEvaluationResultV1:
 evaluation_result_id:str;requested_transition_id:str;source_position_id:str;source_lifecycle_state_id:str;observation_id:str;status:str;position_decision:str;resulting_position:PaperTradePositionV1|None;resulting_lifecycle_state:PaperTradeLifecycleStateV1;generated_exit_fills:tuple[PaperTradeFillV1,...];pnl_evidence:PaperTradePnlEvidenceV1|None;stop_triggered:bool=False;target_1_triggered:bool=False;target_2_triggered:bool=False;target_3_triggered:bool=False;session_close_triggered:bool=False;expiry_close_triggered:bool=False;invalidation_triggered:bool=False;cancellation_triggered:bool=False;runner_close_triggered:bool=False;evaluated_option_price:float=0.;observation_fresh:bool=True;observation_order_valid:bool=True;blockers:tuple[str,...]=();decision_reasons:tuple[str,...]=();warnings:tuple[str,...]=();metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str='PAPER';live_execution_eligible:bool=False;schema_version:str='1.0'
 def __post_init__(self):
  for n in ('evaluation_result_id','requested_transition_id','source_position_id','source_lifecycle_state_id','observation_id'):object.__setattr__(self,n,_nonblank_text(getattr(self,n),n))
  if self.status not in {'BLOCKED','OPEN','PARTIALLY_EXITED','CLOSED_TARGET_1','CLOSED_TARGET_2','CLOSED_TARGET_3','CLOSED_STOP','CLOSED_INVALIDATED','CLOSED_SESSION','CLOSED_EXPIRY','CANCELLED'} or self.position_decision not in {'BLOCK','HOLD','PARTIAL_EXIT','CLOSE_TARGET_1','CLOSE_TARGET_2','CLOSE_TARGET_3','CLOSE_STOP','CLOSE_INVALIDATED','CLOSE_SESSION','CLOSE_EXPIRY','CANCEL'}:raise ValueError('vocabulary')
  if type(self.resulting_lifecycle_state)is not PaperTradeLifecycleStateV1:raise TypeError('resulting_lifecycle_state')
  if self.status=='BLOCKED' and (not self.blockers or self.resulting_position is not None):raise ValueError('blocked')
  if self.status!='BLOCKED' and type(self.resulting_position)is not PaperTradePositionV1:raise ValueError('result')
  if self.status!='BLOCKED' and self.pnl_evidence is None and not (self.position_decision=='HOLD' and not self.generated_exit_fills):raise ValueError('pnl_evidence')
  if self.pnl_evidence is not None and type(self.pnl_evidence)is not PaperTradePnlEvidenceV1:raise TypeError('pnl_evidence')
  if self.status!='BLOCKED' and (self.resulting_lifecycle_state.current_state!=self.status or self.resulting_position.lifecycle_state!=self.resulting_lifecycle_state.current_state):raise ValueError('lifecycle state')
  if type(self.generated_exit_fills)is not tuple or any(type(x)is not PaperTradeFillV1 for x in self.generated_exit_fills):raise TypeError('fills')
  for n in ('stop_triggered','target_1_triggered','target_2_triggered','target_3_triggered','session_close_triggered','expiry_close_triggered','invalidation_triggered','cancellation_triggered','runner_close_triggered','observation_fresh','observation_order_valid'):
   if type(getattr(self,n))is not bool:raise TypeError(n)
  if self.status=='CANCELLED' and (self.position_decision!='CANCEL' or not self.cancellation_triggered or not any(x.fill_reason=='CANCELLED' and x.target_name is None for x in self.generated_exit_fills) or self.stop_triggered or self.target_1_triggered or self.target_2_triggered or self.target_3_triggered or self.invalidation_triggered):raise ValueError('cancellation')
  object.__setattr__(self,'blockers',_freeze_warnings(self.blockers));object.__setattr__(self,'decision_reasons',_freeze_warnings(self.decision_reasons));object.__setattr__(self,'warnings',_freeze_warnings(self.warnings));object.__setattr__(self,'metadata',_freeze_json_value(self.metadata))
  if self.execution_mode!='PAPER'or self.live_execution_eligible is not False or self.schema_version!='1.0':raise ValueError('paper')
 @property
 def resulting_lifecycle_state_name(self):return self.resulting_lifecycle_state.current_state
 def to_dict(self):return {n:([x.to_dict()for x in self.generated_exit_fills]if n=='generated_exit_fills'else self.resulting_position.to_dict()if n=='resulting_position'and self.resulting_position else self.pnl_evidence.to_dict()if n=='pnl_evidence'and self.pnl_evidence else self.resulting_lifecycle_state.to_dict()if n=='resulting_lifecycle_state'else list(getattr(self,n))if n in {'blockers','decision_reasons','warnings'}else _plain_json_value(self.metadata)if n=='metadata'else getattr(self,n))for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False)
 def semantic_dict(self):
  d=self.to_dict();d.pop('evaluation_result_id');d['resulting_lifecycle_state']=self.resulting_lifecycle_state.semantic_dict();return d
