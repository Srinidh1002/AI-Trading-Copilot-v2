from dataclasses import dataclass
from datetime import datetime
from services.contracts.timeframe_evidence_v1 import TimeframeEvidenceV1
@dataclass(frozen=True,slots=True)
class MultiTimeframeSnapshotV1:
 multi_timeframe_snapshot_id:str;created_at:datetime;underlying_symbol:str;exchange:str;required_timeframes:tuple[str,...];timeframe_evidence:tuple[TimeframeEvidenceV1,...];anchor_timeframe:str;synchronization_reference_at:datetime|None;execution_mode:str="PAPER";live_execution_eligible:bool=False;blockers:tuple[str,...]=();warnings:tuple[str,...]=();schema_version:str="multi_timeframe_snapshot.v1"
 def __post_init__(self):
  names=tuple(v.timeframe for v in self.timeframe_evidence)
  if not self.multi_timeframe_snapshot_id or not isinstance(self.created_at,datetime) or not self.created_at.tzinfo or self.anchor_timeframe not in self.required_timeframes or len(set(names))!=len(names) or any((v.underlying_symbol,v.exchange)!=(self.underlying_symbol,self.exchange) or v.timeframe not in self.required_timeframes for v in self.timeframe_evidence) or names!=tuple(t for t in self.required_timeframes if t in names) or self.execution_mode!="PAPER" or self.live_execution_eligible is not False:raise ValueError("Invalid multi-timeframe snapshot.")
  if set(self.required_timeframes)-set(names) and not self.blockers:raise ValueError("Missing timeframe requires blocker.")
  object.__setattr__(self,"blockers",tuple(self.blockers));object.__setattr__(self,"warnings",tuple(self.warnings))
