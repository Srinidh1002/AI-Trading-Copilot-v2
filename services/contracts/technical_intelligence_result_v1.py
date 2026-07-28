"""Paper-only aggregate technical intelligence result."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
import math
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES
from .timeframe_technical_evidence_v1 import TimeframeTechnicalEvidenceV1
_T=("5m","15m","1h","1d");_STATUSES={"READY","READY_WITH_WARNINGS","MISSING_TIMEFRAMES","STALE","FUTURE","INCOMPLETE","INSUFFICIENT_HISTORY","CONFLICTING","MALFORMED","UNSUPPORTED","FAILED"};_BIASES={"BULLISH","BEARISH","NEUTRAL","MIXED","UNAVAILABLE"}
@dataclass(frozen=True,slots=True)
class TechnicalIntelligenceResultV1:
 technical_intelligence_result_id:str;created_at:datetime;multi_timeframe_snapshot_id:str;multi_timeframe_quality_result_id:str;underlying_symbol:str;exchange:str;timeframe_evidence:tuple[TimeframeTechnicalEvidenceV1,...];status:str;aggregate_bias:str;aggregate_strength:float;blockers:tuple[str,...]=();warnings:tuple[str,...]=();execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="technical_intelligence_result.v1";required_timeframes:tuple[str,...]=();bullish_timeframes:tuple[str,...]=();bearish_timeframes:tuple[str,...]=();neutral_timeframes:tuple[str,...]=();unavailable_timeframes:tuple[str,...]=();aligned_timeframes:tuple[str,...]=();conflicting_timeframes:tuple[str,...]=();valid_indicator_count:int=0;unavailable_indicator_count:int=0
 def __post_init__(self):
  evidence=tuple(self.timeframe_evidence);names=tuple(x.timeframe for x in evidence)
  if (not self.technical_intelligence_result_id or not self.multi_timeframe_snapshot_id or not self.multi_timeframe_quality_result_id or not isinstance(self.created_at,datetime) or not self.created_at.tzinfo or (self.underlying_symbol,self.exchange) not in SUPPORTED_MARKET_IDENTITIES or self.status not in _STATUSES or self.aggregate_bias not in _BIASES or isinstance(self.aggregate_strength,bool) or not isinstance(self.aggregate_strength,(int,float)) or not math.isfinite(self.aggregate_strength) or not 0<=self.aggregate_strength<=1 or self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="technical_intelligence_result.v1"):raise ValueError("Invalid technical intelligence result.")
  required=tuple(self.required_timeframes) or names
  if (not required or any(x not in _T for x in required) or len(set(required))!=len(required) or required!=tuple(x for x in _T if x in required) or any(not isinstance(x,TimeframeTechnicalEvidenceV1) or (x.underlying_symbol,x.exchange)!=(self.underlying_symbol,self.exchange) for x in evidence) or len(set(names))!=len(names) or names!=tuple(x for x in required if x in names)):raise ValueError("Invalid result evidence.")
  groups=[tuple(x) for x in (self.bullish_timeframes,self.bearish_timeframes,self.neutral_timeframes,self.unavailable_timeframes)]
  if not any(groups):
   unavailable=tuple(x.timeframe for x in evidence if x.blockers or x.trend_bias=="UNAVAILABLE" and x.momentum_bias=="UNAVAILABLE");neutral=tuple(x for x in required if x not in unavailable);groups=[(),(),neutral,unavailable];object.__setattr__(self,"neutral_timeframes",neutral);object.__setattr__(self,"unavailable_timeframes",unavailable)
  flattened=tuple(x for g in groups for x in g)
  if any(x not in required for x in flattened) or len(set(flattened))!=len(flattened) or set(flattened)!=set(required):raise ValueError("Invalid timeframe classifications.")
  aligned,conflicting=tuple(self.aligned_timeframes),tuple(self.conflicting_timeframes)
  if any(x not in required for x in aligned+conflicting) or len(set(aligned))!=len(aligned) or len(set(conflicting))!=len(conflicting):raise ValueError("Invalid timeframe alignment.")
  valid=sum(x.valid_indicator_count for x in evidence);unavailable=sum(x.unavailable_indicator_count for x in evidence)
  if evidence and self.valid_indicator_count==0 and self.unavailable_indicator_count==0:object.__setattr__(self,"valid_indicator_count",valid);object.__setattr__(self,"unavailable_indicator_count",unavailable)
  if self.valid_indicator_count<0 or self.unavailable_indicator_count<0 or (evidence and (self.valid_indicator_count,self.unavailable_indicator_count)!=(valid,unavailable)):raise ValueError("Invalid aggregate indicator counts.")
  if self.status=="READY" and (self.blockers or self.warnings or self.unavailable_timeframes):raise ValueError("Ready result cannot contain blockers, warnings, or unavailable timeframes.")
  if self.status=="READY_WITH_WARNINGS" and (self.blockers or not self.warnings):raise ValueError("Warning result must contain warnings only.")
  if self.status not in {"READY","READY_WITH_WARNINGS"} and (not self.blockers or self.aggregate_strength!=0):raise ValueError("Blocked result requires blocker and zero strength.")
  for n,v in (("timeframe_evidence",evidence),("required_timeframes",required),("bullish_timeframes",groups[0]),("bearish_timeframes",groups[1]),("neutral_timeframes",groups[2]),("unavailable_timeframes",groups[3]),("aligned_timeframes",aligned),("conflicting_timeframes",conflicting),("blockers",tuple(self.blockers)),("warnings",tuple(self.warnings))):object.__setattr__(self,n,v)
 def to_dict(self):
  return {n:([x.to_dict() for x in self.timeframe_evidence] if n=="timeframe_evidence" else self.created_at.isoformat() if n=="created_at" else list(getattr(self,n)) if isinstance(getattr(self,n),tuple) else getattr(self,n)) for n in self.__dataclass_fields__}
