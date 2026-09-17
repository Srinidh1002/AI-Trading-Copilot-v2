from dataclasses import replace
from threading import RLock
from services.contracts.paper_execution_observation_v1 import PaperExecutionObservationV1
class PaperExecutionObservationRepositoryError(ValueError):pass
class DuplicatePaperExecutionObservationError(PaperExecutionObservationRepositoryError):pass
class PaperExecutionObservationNotFoundError(PaperExecutionObservationRepositoryError):pass
class InMemoryPaperExecutionObservationRepository:
 def __init__(self):self._items={};self._lock=RLock()
 def _copy(self,v):
  if not isinstance(v,PaperExecutionObservationV1):raise PaperExecutionObservationRepositoryError("observation must be PaperExecutionObservationV1.")
  return replace(v)
 def _list(self,values):return tuple(replace(v) for v in sorted(values,key=lambda x:(x.observed_at,x.observation_id)))
 def save(self,observation):
  v=self._copy(observation)
  with self._lock:
   if v.observation_id in self._items:raise DuplicatePaperExecutionObservationError("observation_id already exists.")
   self._items[v.observation_id]=v
  return replace(v)
 def save_many(self,observations):
  values=tuple(self._copy(v) for v in observations)
  with self._lock:
   ids=[v.observation_id for v in values]
   if len(set(ids))!=len(ids) or any(i in self._items for i in ids):raise DuplicatePaperExecutionObservationError("observation_id already exists.")
   self._items.update({v.observation_id:v for v in values})
  return self._list(values)
 def get(self,observation_id):
  with self._lock:return replace(self._items[observation_id]) if observation_id in self._items else None
 def contains(self,observation_id):
  with self._lock:return observation_id in self._items
 def list_all(self):
  with self._lock:return self._list(self._items.values())
 snapshot=list_all
 def list_by_stage(self,stage):return tuple(v for v in self.list_all() if v.stage==stage)
 def list_by_outcome(self,outcome):return tuple(v for v in self.list_all() if v.outcome==outcome)
 def list_by_execution_request_id(self,value):return tuple(v for v in self.list_all() if v.execution_request_id==value)
 def list_by_canonical_execution_result_id(self,value):return tuple(v for v in self.list_all() if v.canonical_execution_result_id==value)
 def list_by_order_id(self,value):return tuple(v for v in self.list_all() if v.paper_order_id==value)
 def list_by_identity(self,symbol,exchange=None):
  from services.core.market_identity import normalize_market_identity
  pair=normalize_market_identity(symbol,exchange)
  if pair is None:raise PaperExecutionObservationRepositoryError("Unsupported market identity.")
  return tuple(v for v in self.list_all() if (v.underlying_symbol,v.exchange)==pair)
 def count(self):
  with self._lock:return len(self._items)
 def clear(self):
  with self._lock:self._items.clear()
