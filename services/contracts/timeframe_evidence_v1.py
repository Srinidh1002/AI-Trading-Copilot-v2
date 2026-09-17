from dataclasses import dataclass
from datetime import datetime
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES
@dataclass(frozen=True,slots=True)
class TimeframeEvidenceV1:
 timeframe_evidence_id:str;created_at:datetime;underlying_symbol:str;exchange:str;timeframe:str;candle_series_id:str;quality_result_id:str;quality_status:str;candle_count:int;complete_candle_count:int;incomplete_candle_count:int;first_candle_start_at:datetime|None;latest_candle_start_at:datetime|None;latest_candle_end_at:datetime|None;latest_complete_candle_end_at:datetime|None;age_seconds:float|None;freshness_threshold_seconds:float|None;minimum_required_candles:int;history_sufficient:bool;latest_candle_complete:bool|None;blockers:tuple[str,...]=();warnings:tuple[str,...]=();execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="timeframe_evidence.v1"
 def __post_init__(self):
  bad={"STALE","FUTURE","EMPTY","MALFORMED","INCOMPLETE","CONFLICTING","UNSUPPORTED","FAILED"}
  if not self.timeframe_evidence_id or (self.underlying_symbol,self.exchange) not in SUPPORTED_MARKET_IDENTITIES or self.timeframe not in {"1m","3m","5m","15m","30m","1h","1d"} or not isinstance(self.created_at,datetime) or not self.created_at.tzinfo or self.candle_count<0 or self.complete_candle_count+self.incomplete_candle_count!=self.candle_count or self.minimum_required_candles<=0 or self.history_sufficient!=(self.complete_candle_count>=self.minimum_required_candles) or (self.quality_status in bad and not self.blockers) or self.execution_mode!="PAPER" or self.live_execution_eligible is not False:raise ValueError("Invalid timeframe evidence.")
  object.__setattr__(self,"blockers",tuple(self.blockers));object.__setattr__(self,"warnings",tuple(self.warnings))
