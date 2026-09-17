from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import datetime
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES
_STATUSES={"MATCHED","MISMATCHED","INCOMPLETE","NOT_REPLAYABLE","FAILED"}
@dataclass(frozen=True,slots=True)
class PaperExecutionReplayResultV1:
 replay_result_id:str;created_at:datetime;replay_status:str;canonical_execution_result_id:str|None=None;execution_request_id:str|None=None;authorization_id:str|None=None;execution_result_id:str|None=None;paper_order_id:str|None=None;idempotency_key:str|None=None;underlying_symbol:str|None=None;exchange:str|None=None;action:str|None=None;option_type:str|None=None;position_side:str|None=None;trading_symbol:str|None=None;quantity:int|None=None;lots:int|None=None;expected_pipeline_status:str|None=None;observed_pipeline_status:str|None=None;expected_execution_status:str|None=None;observed_execution_status:str|None=None;expected_fill_price:float|None=None;observed_fill_price:float|None=None;compared_observation_count:int=0;matched_field_count:int=0;mismatched_fields:tuple[str,...]=();blockers:tuple[str,...]=();warnings:tuple[str,...]=();schema_version:str="paper_execution_replay_result.v1";execution_mode:str="PAPER";live_execution_eligible:bool=False
 def __post_init__(self):
  if not isinstance(self.replay_result_id,str) or not self.replay_result_id or not isinstance(self.created_at,datetime) or self.created_at.tzinfo is None or self.replay_status not in _STATUSES or self.schema_version!="paper_execution_replay_result.v1" or self.execution_mode!="PAPER" or self.live_execution_eligible is not False:raise ValueError("Invalid replay result controls.")
  m,b,w=tuple(sorted(set(self.mismatched_fields))),tuple(self.blockers),tuple(self.warnings)
  if any(not isinstance(x,str) or not x for x in m+b+w) or self.compared_observation_count<0 or self.matched_field_count<0:raise ValueError("Invalid replay evidence.")
  object.__setattr__(self,"mismatched_fields",m);object.__setattr__(self,"blockers",b);object.__setattr__(self,"warnings",w)
  pair=(self.underlying_symbol,self.exchange)
  if (pair[0] is None)!=(pair[1] is None) or (pair[0] is not None and pair not in SUPPORTED_MARKET_IDENTITIES):raise ValueError("Invalid canonical market identity.")
  if self.replay_status=="MATCHED" and (m or b or self.compared_observation_count<=0):raise ValueError("Invalid matched replay.")
  if self.replay_status=="MISMATCHED" and not m:raise ValueError("Mismatch fields are required.")
  if self.replay_status in {"INCOMPLETE","NOT_REPLAYABLE","FAILED"} and not b:raise ValueError("Replay blockers are required.")
 def to_dict(self):return {n:(getattr(self,n).isoformat() if isinstance(getattr(self,n),datetime) else list(getattr(self,n)) if n in {"mismatched_fields","blockers","warnings"} else getattr(self,n)) for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
