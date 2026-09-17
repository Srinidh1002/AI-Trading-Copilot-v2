"""Immutable, bounded observation of an already-completed paper stage."""
from __future__ import annotations
import json, math
from dataclasses import dataclass
from datetime import datetime
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES
_STAGES={"RISK","CANDIDATE","REQUEST","AUTHORIZATION","EXECUTION","ORDER_STATE","PIPELINE_RESULT"}; _OUTCOMES={"APPROVED","NO_ACTION","BLOCKED","AUTHORIZED","EXECUTED","DUPLICATE","REJECTED","FAILED","RECORDED"}
def _aware(v,n):
 if not isinstance(v,datetime) or v.tzinfo is None: raise ValueError(f"{n} must be timezone-aware.")
def _texts(values):
 values=tuple(values)
 if any(not isinstance(x,str) or not x for x in values):raise ValueError("Invalid blockers or warnings.")
 return values
@dataclass(frozen=True,slots=True)
class PaperExecutionObservationV1:
 observation_id:str; observed_at:datetime; stage:str; outcome:str
 snapshot_id:str|None=None;analysis_id:str|None=None;decision_id:str|None=None;trade_plan_result_id:str|None=None;trade_plan_id:str|None=None;sizing_result_id:str|None=None;canonical_risk_result_id:str|None=None;paper_candidate_id:str|None=None;execution_request_id:str|None=None;authorization_id:str|None=None;authorization_result_id:str|None=None;execution_result_id:str|None=None;paper_order_id:str|None=None;canonical_execution_result_id:str|None=None;idempotency_key:str|None=None
 underlying_symbol:str|None=None;exchange:str|None=None;action:str|None=None;option_type:str|None=None;position_side:str|None=None;trading_symbol:str|None=None;quantity:int|None=None;lots:int|None=None;reference_price:float|None=None;fill_price:float|None=None;capital_required:float|None=None;maximum_loss:float|None=None;submitted_at:datetime|None=None;filled_at:datetime|None=None;blockers:tuple[str,...]=();warnings:tuple[str,...]=();schema_version:str="paper_execution_observation.v1";execution_mode:str="PAPER";live_execution_eligible:bool=False
 def __post_init__(self):
  if not isinstance(self.observation_id,str) or not self.observation_id or self.stage not in _STAGES or self.outcome not in _OUTCOMES or self.schema_version!="paper_execution_observation.v1" or self.execution_mode!="PAPER" or self.live_execution_eligible is not False:raise ValueError("Invalid paper execution observation controls.")
  _aware(self.observed_at,"observed_at")
  for n in ("submitted_at","filled_at"):
   if getattr(self,n) is not None:_aware(getattr(self,n),n)
  b,w=_texts(self.blockers),_texts(self.warnings);object.__setattr__(self,"blockers",b);object.__setattr__(self,"warnings",w)
  identity=(self.underlying_symbol,self.exchange)
  if (identity[0] is None)!=(identity[1] is None) or (identity[0] is not None and identity not in SUPPORTED_MARKET_IDENTITIES):raise ValueError("Invalid canonical market identity.")
  direction=(self.action,self.option_type,self.position_side)
  if any(x is not None for x in direction) and direction not in {("BUY","CALL","LONG"),("SELL","PUT","LONG")} :raise ValueError("Invalid long-premium direction.")
  for n in ("quantity","lots"):
   v=getattr(self,n)
   if v is not None and (isinstance(v,bool) or not isinstance(v,int) or v<=0):raise ValueError(f"{n} must be positive.")
  for n in ("reference_price","fill_price","capital_required","maximum_loss"):
   v=getattr(self,n)
   if v is not None and (isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0):raise ValueError(f"{n} must be positive.")
  if self.outcome=="EXECUTED" and (not self.execution_result_id or self.fill_price is None or self.filled_at is None or self.blockers):raise ValueError("Executed observation requires fill evidence.")
  if self.outcome=="DUPLICATE" and (not self.execution_request_id or not self.idempotency_key or self.fill_price is not None):raise ValueError("Duplicate observation is invalid.")
  if self.outcome in {"BLOCKED","REJECTED","FAILED"} and not self.blockers:raise ValueError("Blocked observation requires blockers.")
 def to_dict(self):return {n:(getattr(self,n).isoformat() if isinstance(getattr(self,n),datetime) else list(getattr(self,n)) if n in {"blockers","warnings"} else getattr(self,n)) for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
 def semantic_dict(self):d=self.to_dict();d.pop("observation_id");d.pop("observed_at");return d
