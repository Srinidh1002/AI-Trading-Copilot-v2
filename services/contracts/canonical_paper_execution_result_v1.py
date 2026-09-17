"""Immutable bounded outcome of one explicit canonical paper execution."""
from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import datetime
_STATUSES={"EXECUTED","NO_ACTION","PREPARATION_BLOCKED","REQUEST_BLOCKED","AUTHORIZATION_BLOCKED","EXECUTION_BLOCKED","DUPLICATE","FAILED"}
@dataclass(frozen=True,slots=True)
class CanonicalPaperExecutionResultV1:
 canonical_execution_result_id:str;created_at:datetime;pipeline_status:str; snapshot_id:str|None=None;analysis_id:str|None=None;decision_id:str|None=None;trade_plan_result_id:str|None=None;trade_plan_id:str|None=None;sizing_result_id:str|None=None;canonical_risk_result_id:str|None=None;paper_candidate_id:str|None=None;execution_request_id:str|None=None;authorization_id:str|None=None;authorization_result_id:str|None=None;execution_result_id:str|None=None;idempotency_key:str|None=None;underlying_symbol:str|None=None;exchange:str|None=None;action:str|None=None;option_type:str|None=None;position_side:str|None=None;trading_symbol:str|None=None;quantity:int|None=None;lots:int|None=None;preparation_status:str|None=None;authorization_status:str|None=None;execution_status:str|None=None;reference_price:float|None=None;fill_price:float|None=None;capital_used:float|None=None;realized_maximum_loss:float|None=None;submitted_at:datetime|None=None;filled_at:datetime|None=None;blockers:tuple[str,...]=();warnings:tuple[str,...]=();schema_version:str="canonical_paper_execution_result.v1";execution_mode:str="PAPER";live_execution_eligible:bool=False
 def __post_init__(self):
  if not self.canonical_execution_result_id or not isinstance(self.created_at,datetime) or self.created_at.tzinfo is None or self.pipeline_status not in _STATUSES or self.schema_version!="canonical_paper_execution_result.v1" or self.execution_mode!="PAPER" or self.live_execution_eligible is not False:raise ValueError("Invalid canonical execution result.")
  b,w=tuple(self.blockers),tuple(self.warnings);object.__setattr__(self,"blockers",b);object.__setattr__(self,"warnings",w)
  if any(not isinstance(x,str) or not x for x in b+w):raise ValueError("Invalid blockers or warnings.")
  fill=(self.reference_price,self.fill_price,self.capital_used,self.realized_maximum_loss,self.submitted_at,self.filled_at)
  if self.pipeline_status=="EXECUTED":
   if self.execution_status!="FILLED" or not all((self.execution_request_id,self.authorization_id,self.execution_result_id,self.underlying_symbol,self.exchange,self.action,self.option_type,self.position_side,self.trading_symbol,self.quantity,self.lots)) or any(x is None for x in fill) or b:raise ValueError("Invalid executed result.")
  elif self.pipeline_status=="DUPLICATE":
   if self.execution_status!="DUPLICATE" or not self.execution_request_id or not self.idempotency_key or not (b or w) or any(x is not None for x in fill):raise ValueError("Invalid duplicate result.")
  elif not b or any(x is not None for x in fill):raise ValueError("Non-executed result requires blockers and no fills.")
 def to_dict(self):return {n:(getattr(self,n).isoformat() if isinstance(getattr(self,n),datetime) else list(getattr(self,n)) if n in {"blockers","warnings"} else getattr(self,n)) for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
 def semantic_dict(self):d=self.to_dict();d.pop("canonical_execution_result_id");d.pop("created_at");return d
