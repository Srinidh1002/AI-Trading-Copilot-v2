"""Adapter-owned persistence using the existing atomic PaperTradeRepository."""
from __future__ import annotations
from services.paper_trade_repository import PaperTradeRepository
from services.contracts.paper_trade_persistence_snapshot_v1 import PaperTradePersistenceSnapshotV1

class PaperTradePersistenceService:
 def __init__(self,repository):
  if not isinstance(repository,PaperTradeRepository):raise TypeError('repository must be PaperTradeRepository')
  self.repository=repository
 def save(self,snapshot):
  if type(snapshot)is not PaperTradePersistenceSnapshotV1:raise TypeError('snapshot')
  state={'trade_id':snapshot.paper_trade_id,'status':'OPEN' if not snapshot.lifecycle_state.is_terminal else 'CLOSED','typed_p7_snapshot':snapshot.to_dict(),'typed_p7_integrity_hash':snapshot.integrity_hash}
  self.repository.save_trade(state);return snapshot
 def get(self,paper_trade_id):
  state=self.repository.get_trade(paper_trade_id)
  if state is None:return None
  raw=state.get('typed_p7_snapshot')
  if type(raw)is not dict:raise ValueError('typed_p7_snapshot missing')
  snapshot=PaperTradePersistenceSnapshotV1.from_dict(raw)
  if state.get('typed_p7_integrity_hash')!=snapshot.integrity_hash:raise ValueError('typed snapshot integrity mismatch')
  return snapshot
 def list_all(self):
  values=[]
  for state in self.repository.get_all_trades():
   if 'typed_p7_snapshot' in state:values.append(self.get(state['trade_id']))
  return tuple(sorted(values,key=lambda x:(x.created_at,x.paper_trade_id)))
 def list_active(self):return tuple(x for x in self.list_all() if not x.lifecycle_state.is_terminal)
 def get_by_trade_plan_id(self,trade_plan_id):return tuple(x for x in self.list_all() if x.lifecycle_state.trade_plan_id==trade_plan_id)
 def get_by_idempotency_key(self,key):
  values=[x for x in self.list_all() if x.adapter_idempotency_key==key]
  if len(values)>1:raise ValueError('duplicate durable idempotency key')
  return values[0] if values else None
