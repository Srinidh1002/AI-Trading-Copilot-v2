"""Bounded in-memory idempotency claims for deterministic paper execution."""
class InMemoryPaperExecutionIdempotencyStore:
    def __init__(self): self._claims={}
    def get(self,key): return self._claims.get(key)
    def claim(self,key,result_id):
        if key in self._claims: return False
        self._claims[key]={"execution_result_id":result_id,"execution_status":"FILLED"}; return True
