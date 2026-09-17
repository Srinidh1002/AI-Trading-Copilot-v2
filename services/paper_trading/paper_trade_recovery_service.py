"""Fail-closed recovery of adapter-owned typed snapshots."""
from __future__ import annotations
from .paper_trade_persistence_service import PaperTradePersistenceService
class PaperTradeRecoveryService:
 def __init__(self,persistence_service):
  if type(persistence_service)is not PaperTradePersistenceService:raise TypeError('persistence_service')
  self.persistence_service=persistence_service
 def recover(self,include_terminal=True):
  snapshots=self.persistence_service.list_all();seen_keys=set();seen_positions=set();recovered=[]
  for snapshot in snapshots:
   if snapshot.adapter_idempotency_key in seen_keys:raise ValueError('duplicate idempotency key')
   seen_keys.add(snapshot.adapter_idempotency_key)
   if snapshot.position is not None:
    if snapshot.position.position_id in seen_positions:raise ValueError('duplicate position')
    seen_positions.add(snapshot.position.position_id)
   if include_terminal or not snapshot.lifecycle_state.is_terminal:recovered.append(snapshot)
  return tuple(recovered)
 def recover_active(self):return self.recover(include_terminal=False)
