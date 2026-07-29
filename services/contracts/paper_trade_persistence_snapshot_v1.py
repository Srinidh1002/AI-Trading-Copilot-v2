"""Canonical, JSON-only persistence envelope for typed P7 PAPER state."""
from __future__ import annotations
import hashlib,json
from dataclasses import dataclass
from datetime import date,datetime
from typing import Any
from .paper_trade_lifecycle_policy_v1 import PaperTradeLifecyclePolicyV1
from .paper_trade_lifecycle_state_v1 import PaperTradeLifecycleStateV1
from .paper_trade_position_v1 import PaperTradePositionV1
from .paper_trade_fill_v1 import PaperTradeFillV1
from .paper_trade_pnl_evidence_v1 import PaperTradePnlEvidenceV1
from .paper_market_observation_v1 import PaperMarketObservationV1

def _text(v,n):
 if type(v)is not str or not v.strip():raise ValueError(n)
 return v.strip()
def _dt(v,n):
 if not isinstance(v,datetime) or v.tzinfo is None:raise ValueError(n)
 return v
def _load_dt(v):return datetime.fromisoformat(v) if type(v)is str else v
def _restore_fill(d):
 x=dict(d);x['filled_at']=_load_dt(x['filled_at'])
 for n in ('warnings','decision_reasons','blockers'):
  if n in x:x[n]=tuple(x[n])
 return PaperTradeFillV1(**x)
def _restore_position(d):
 x=dict(d);x['opened_at']=_load_dt(x['opened_at']);x['entry_fill']=_restore_fill(x['entry_fill']);x['exit_fills']=tuple(_restore_fill(v) for v in x['exit_fills']);
 for n in ('blockers','decision_reasons','warnings'):x[n]=tuple(x[n])
 return PaperTradePositionV1(**x)
def _restore_policy(d):
 x=dict(d);x['policy_timestamp']=_load_dt(x['policy_timestamp']);x['source_timestamps']={k:_load_dt(v) for k,v in x['source_timestamps'].items()};x['warnings']=tuple(x['warnings']);return PaperTradeLifecyclePolicyV1(**x)
def _restore_state(d):
 x=dict(d)
 for n in ('lifecycle_created_at','last_observation_timestamp','waiting_for_entry_at','opened_at','partially_exited_at','closed_at','cancelled_at','blocked_at'):
  if x.get(n)is not None:x[n]=_load_dt(x[n])
 for n in ('blockers','decision_reasons','warnings'):x[n]=tuple(x[n])
 return PaperTradeLifecycleStateV1(**x)
def _restore_observation(d):
 x=dict(d);x['observed_at']=_load_dt(x['observed_at']);x['received_at']=_load_dt(x['received_at']);x['market_session_date']=date.fromisoformat(x['market_session_date']);x['source_timestamps']={k:_load_dt(v) for k,v in x['source_timestamps'].items()};x['warnings']=tuple(x['warnings']);return PaperMarketObservationV1(**x)
def _restore_pnl(d):
 x=dict(d);x['calculated_at']=_load_dt(x['calculated_at']);x['warnings']=tuple(x['warnings']);return PaperTradePnlEvidenceV1(**x)

@dataclass(frozen=True,slots=True)
class PaperTradePersistenceSnapshotV1:
 paper_trade_id:str;adapter_idempotency_key:str;idempotency_payload_hash:str;lifecycle_policy:PaperTradeLifecyclePolicyV1;lifecycle_state:PaperTradeLifecycleStateV1;position:PaperTradePositionV1|None;latest_observation:PaperMarketObservationV1|None;pnl_evidence:PaperTradePnlEvidenceV1|None;created_at:datetime;updated_at:datetime;legacy_trade_id:str|None=None;event_sequence:int=0;schema_version:str='1.0';execution_mode:str='PAPER';live_execution_eligible:bool=False
 def __post_init__(self):
  for n in ('paper_trade_id','adapter_idempotency_key','idempotency_payload_hash'):object.__setattr__(self,n,_text(getattr(self,n),n))
  if self.legacy_trade_id is not None:object.__setattr__(self,'legacy_trade_id',_text(self.legacy_trade_id,'legacy_trade_id'))
  if type(self.lifecycle_policy)is not PaperTradeLifecyclePolicyV1 or type(self.lifecycle_state)is not PaperTradeLifecycleStateV1:raise TypeError('typed lifecycle')
  if self.position is not None and type(self.position)is not PaperTradePositionV1:raise TypeError('position')
  if self.latest_observation is not None and type(self.latest_observation)is not PaperMarketObservationV1:raise TypeError('observation')
  if self.pnl_evidence is not None and type(self.pnl_evidence)is not PaperTradePnlEvidenceV1:raise TypeError('pnl')
  if self.position is not None and (self.position.lifecycle_state!=self.lifecycle_state.current_state or self.position.lifecycle_policy_id!=self.lifecycle_policy.lifecycle_policy_id):raise ValueError('lifecycle position coherence')
  if self.position is not None and self.latest_observation is not None and self.position.trade_plan_id!=self.latest_observation.trade_plan_id:raise ValueError('observation identity')
  if self.pnl_evidence is not None and (self.position is None or self.pnl_evidence.position_id!=self.position.position_id):raise ValueError('pnl identity')
  object.__setattr__(self,'created_at',_dt(self.created_at,'created_at'));object.__setattr__(self,'updated_at',_dt(self.updated_at,'updated_at'))
  if self.updated_at<self.created_at or type(self.event_sequence)is not int or isinstance(self.event_sequence,bool) or self.event_sequence<0:raise ValueError('event sequence')
  if self.schema_version!='1.0'or self.execution_mode!='PAPER'or self.live_execution_eligible is not False:raise ValueError('paper')
 def to_dict(self):
  return {'paper_trade_id':self.paper_trade_id,'adapter_idempotency_key':self.adapter_idempotency_key,'idempotency_payload_hash':self.idempotency_payload_hash,'lifecycle_policy':self.lifecycle_policy.to_dict(),'lifecycle_state':self.lifecycle_state.to_dict(),'position':self.position.to_dict()if self.position else None,'latest_observation':self.latest_observation.to_dict()if self.latest_observation else None,'pnl_evidence':self.pnl_evidence.to_dict()if self.pnl_evidence else None,'created_at':self.created_at.isoformat(),'updated_at':self.updated_at.isoformat(),'legacy_trade_id':self.legacy_trade_id,'event_sequence':self.event_sequence,'schema_version':self.schema_version,'execution_mode':self.execution_mode,'live_execution_eligible':self.live_execution_eligible}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False)
 @property
 def integrity_hash(self):return hashlib.sha256(self.to_json().encode()).hexdigest()
 @classmethod
 def from_dict(cls,d):
  if type(d)is not dict:raise TypeError('snapshot')
  required={'paper_trade_id','adapter_idempotency_key','idempotency_payload_hash','lifecycle_policy','lifecycle_state','position','latest_observation','pnl_evidence','created_at','updated_at','event_sequence','schema_version','execution_mode','live_execution_eligible'}
  if not required.issubset(d):raise ValueError('snapshot keys')
  return cls(d['paper_trade_id'],d['adapter_idempotency_key'],d['idempotency_payload_hash'],_restore_policy(d['lifecycle_policy']),_restore_state(d['lifecycle_state']),_restore_position(d['position'])if d['position'] is not None else None,_restore_observation(d['latest_observation'])if d['latest_observation'] is not None else None,_restore_pnl(d['pnl_evidence'])if d['pnl_evidence'] is not None else None,_load_dt(d['created_at']),_load_dt(d['updated_at']),d.get('legacy_trade_id'),d['event_sequence'],d['schema_version'],d['execution_mode'],d['live_execution_eligible'])
