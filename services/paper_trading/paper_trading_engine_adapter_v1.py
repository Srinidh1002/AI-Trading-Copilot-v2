"""Explicit opt-in bridge between P7 typed state and legacy PaperTradingEngine."""
from __future__ import annotations
import hashlib,json
from dataclasses import dataclass
from datetime import datetime
from services.paper_trading_engine import PaperTradingEngine
from services.contracts import PaperTradeEntryEvaluationInputV1,PaperTradePositionEvaluationInputV1,PaperTradeLifecycleStateV1
from .paper_trade_entry_evaluator import evaluate_paper_trade_entry
from .paper_trade_position_evaluator import evaluate_open_paper_trade_position
from .paper_trade_persistence_service import PaperTradePersistenceService
from services.contracts.paper_trade_persistence_snapshot_v1 import PaperTradePersistenceSnapshotV1

def _text(v,n):
 if type(v)is not str or not v.strip():raise ValueError(n)
 return v.strip()
@dataclass(frozen=True,slots=True)
class PaperTradingEngineAdapterInputV1:
 adapter_result_id:str;paper_trade_id:str;idempotency_key:str;operation:str;evaluation_timestamp:datetime;entry_input:PaperTradeEntryEvaluationInputV1|None=None;position_input:PaperTradePositionEvaluationInputV1|None=None;persistence_requested:bool=True;execution_mode:str='PAPER';live_execution_eligible:bool=False
 def __post_init__(self):
  for n in ('adapter_result_id','paper_trade_id','idempotency_key'):object.__setattr__(self,n,_text(getattr(self,n),n))
  if self.operation not in {'EVALUATE_ENTRY','EVALUATE_POSITION','CANCEL_PAPER_TRADE','RECOVER_ONLY'}:raise ValueError('operation')
  if not isinstance(self.evaluation_timestamp,datetime) or self.evaluation_timestamp.tzinfo is None:raise ValueError('evaluation_timestamp')
  if self.operation=='EVALUATE_ENTRY' and type(self.entry_input)is not PaperTradeEntryEvaluationInputV1:raise TypeError('entry_input')
  if self.operation in {'EVALUATE_POSITION','CANCEL_PAPER_TRADE'} and type(self.position_input)is not PaperTradePositionEvaluationInputV1:raise TypeError('position_input')
  if self.operation=='CANCEL_PAPER_TRADE' and self.position_input.cancellation_status!='REQUESTED':raise ValueError('typed cancellation authority required')
  if self.operation=='RECOVER_ONLY' and (self.entry_input is not None or self.position_input is not None):raise ValueError('recover input')
  if type(self.persistence_requested)is not bool or self.execution_mode!='PAPER' or self.live_execution_eligible is not False:raise ValueError('paper')
 def semantic_payload(self):
  source=self.entry_input.to_dict() if self.entry_input else self.position_input.semantic_dict() if self.position_input else {'paper_trade_id':self.paper_trade_id}
  return json.dumps({'operation':self.operation,'paper_trade_id':self.paper_trade_id,'input':source},sort_keys=True,separators=(',',':'),default=str)
@dataclass(frozen=True,slots=True)
class PaperTradingEngineAdapterResultV1:
 adapter_result_id:str;idempotency_key:str;operation:str;status:str;lifecycle_state:object|None;position:object|None;entry_result:object|None;position_result:object|None;legacy_trade_id:str|None;persisted:bool;recovered:bool;duplicate:bool;blockers:tuple[str,...]=()

class PaperTradingEngineAdapterV1:
 """Opt-in only; no legacy caller is routed here automatically."""
 def __init__(self,engine,persistence_service=None):
  if not isinstance(engine,PaperTradingEngine):raise TypeError('engine')
  if persistence_service is not None and type(persistence_service)is not PaperTradePersistenceService:raise TypeError('persistence_service')
  self.engine=engine;self.persistence_service=persistence_service
 def _snapshot(self,i,state,position,observation,pnl,legacy_trade_id=None):
  payload_hash=hashlib.sha256(i.semantic_payload().encode()).hexdigest()
  return PaperTradePersistenceSnapshotV1(i.paper_trade_id,i.idempotency_key,payload_hash,state and (i.entry_input.lifecycle_policy if i.entry_input else i.position_input.lifecycle_policy),state,position,observation,pnl,i.evaluation_timestamp,i.evaluation_timestamp,legacy_trade_id,state.transition_sequence)
 def _duplicate(self,i):
  old=self.persistence_service.get_by_idempotency_key(i.idempotency_key) if self.persistence_service else None
  if old is None:return None
  if old.idempotency_payload_hash!=hashlib.sha256(i.semantic_payload().encode()).hexdigest():return PaperTradingEngineAdapterResultV1(i.adapter_result_id,i.idempotency_key,i.operation,'BLOCKED',old.lifecycle_state,old.position,None,None,old.legacy_trade_id,False,False,False,('IDEMPOTENCY_PAYLOAD_CONFLICT',))
  return PaperTradingEngineAdapterResultV1(i.adapter_result_id,i.idempotency_key,i.operation,old.lifecycle_state.current_state,old.lifecycle_state,old.position,None,None,old.legacy_trade_id,True,False,True)
 def execute(self,i):
  if type(i)is not PaperTradingEngineAdapterInputV1:raise TypeError('adapter_input')
  duplicate=self._duplicate(i)
  if duplicate:return duplicate
  if i.operation=='RECOVER_ONLY':
   old=self.persistence_service.get(i.paper_trade_id) if self.persistence_service else None
   return PaperTradingEngineAdapterResultV1(i.adapter_result_id,i.idempotency_key,i.operation,'RECOVERED' if old else 'BLOCKED',old.lifecycle_state if old else None,old.position if old else None,None,None,old.legacy_trade_id if old else None,False,True,False,() if old else ('SNAPSHOT_NOT_FOUND',))
  if i.operation in {'EVALUATE_POSITION','CANCEL_PAPER_TRADE'}:
   result=evaluate_open_paper_trade_position(i.position_input);snapshot=self._snapshot(i,result.resulting_lifecycle_state,result.resulting_position,i.position_input.observation,result.pnl_evidence)
   if self.persistence_service and i.persistence_requested and result.pnl_evidence is not None:self.persistence_service.save(snapshot)
   return PaperTradingEngineAdapterResultV1(i.adapter_result_id,i.idempotency_key,i.operation,result.status,result.resulting_lifecycle_state,result.resulting_position,None,result,None,bool(self.persistence_service and i.persistence_requested and result.pnl_evidence is not None),False,False,result.blockers)
  result=evaluate_paper_trade_entry(i.entry_input)
  if result.status!='OPEN':return PaperTradingEngineAdapterResultV1(i.adapter_result_id,i.idempotency_key,i.operation,result.status,i.entry_input.lifecycle_state,None,result,None,None,False,False,False,result.blockers)
  p=result.position;option_type='CE' if p.option_type in {'CALL','CE'} else 'PE'
  legacy=self.engine.open_trade({'decision':'TRADE_ALLOWED','direction':p.direction,'contract':{'selected':True,'symbol':p.option_symbol,'option_type':option_type,'strike':p.strike,'expiry':p.expiry,'premium':p.entry_price,'lot_size':p.lot_size},'trade_plan':{'allowed':True,'levels':{'option_entry_price':p.entry_price,'option_stop_loss':p.stop_loss,'option_target':p.target_1},'risk':{'allowed':True,'lots':p.initial_lot_count,'quantity':p.initial_quantity,'required_capital':p.estimated_total_capital_requirement,'estimated_maximum_loss':p.estimated_risk_amount}}},p.underlying_symbol,p.exchange,opened_at=i.evaluation_timestamp,trade_id=i.paper_trade_id)
  source=i.entry_input.lifecycle_state;state=PaperTradeLifecycleStateV1(i.entry_input.requested_transition_id,p.trade_plan_id,p.integrated_trade_plan_result_id,p.lifecycle_policy_id,'OPEN',source.lifecycle_created_at,previous_state=source.current_state,transition_sequence=source.transition_sequence+1,last_transition_code=i.entry_input.requested_transition_id,last_observation_id=i.entry_input.observation.observation_id,last_observation_timestamp=i.entry_input.observation.observed_at,opened_at=i.evaluation_timestamp)
  snapshot=self._snapshot(i,state,p,i.entry_input.observation,None,legacy.trade_id)
  if self.persistence_service and i.persistence_requested:self.persistence_service.save(snapshot)
  return PaperTradingEngineAdapterResultV1(i.adapter_result_id,i.idempotency_key,i.operation,'OPEN',state,p,result,None,legacy.trade_id,bool(self.persistence_service and i.persistence_requested),False,False,())
