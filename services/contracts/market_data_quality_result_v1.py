from dataclasses import dataclass
from datetime import datetime
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES
@dataclass(frozen=True,slots=True)
class MarketDataQualityResultV1:
 quality_result_id:str;created_at:datetime;subject_type:str;quality_status:str;underlying_symbol:str|None=None;exchange:str|None=None;timeframe:str|None=None;source_provider:str|None=None;observed_at:datetime|None=None;received_at:datetime|None=None;age_seconds:float|None=None;freshness_threshold_seconds:float|None=None;item_count:int=0;valid_item_count:int=0;invalid_item_count:int=0;duplicate_item_count:int=0;out_of_order_item_count:int=0;incomplete_item_count:int=0;provider_count:int=0;disagreement_bps:float|None=None;blockers:tuple[str,...]=();warnings:tuple[str,...]=();execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="market_data_quality_result.v1"
 def __post_init__(self):
  bad={"STALE","FUTURE","EMPTY","MALFORMED","INCOMPLETE","CONFLICTING","UNSUPPORTED","FAILED"}
  if not self.quality_result_id or not isinstance(self.created_at,datetime) or not self.created_at.tzinfo or self.subject_type not in {"QUOTE","CANDLE","CANDLE_SERIES","PROVIDER_CONSENSUS"} or self.quality_status not in bad|{"VALID","VALID_WITH_WARNINGS"} or self.execution_mode!="PAPER" or self.live_execution_eligible is not False or any(not isinstance(v,int) or v<0 for v in (self.item_count,self.valid_item_count,self.invalid_item_count,self.duplicate_item_count,self.out_of_order_item_count,self.incomplete_item_count,self.provider_count)) or (self.quality_status in bad and not self.blockers) or (self.quality_status=="VALID" and self.blockers) or (self.quality_status=="VALID_WITH_WARNINGS" and (self.blockers or not self.warnings)):raise ValueError("Invalid quality result.")
  if (self.underlying_symbol is None)!=(self.exchange is None) or (self.underlying_symbol is not None and (self.underlying_symbol,self.exchange) not in SUPPORTED_MARKET_IDENTITIES):raise ValueError("Invalid quality identity.")
  object.__setattr__(self,"blockers",tuple(self.blockers));object.__setattr__(self,"warnings",tuple(self.warnings))
