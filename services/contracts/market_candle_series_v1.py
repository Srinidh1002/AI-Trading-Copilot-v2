from dataclasses import dataclass
from datetime import datetime
from services.contracts.market_candle_v1 import MarketCandleV1
@dataclass(frozen=True,slots=True)
class MarketCandleSeriesV1:
 series_id:str;underlying_symbol:str;exchange:str;timeframe:str;candles:tuple[MarketCandleV1,...];requested_from:datetime|None;requested_until:datetime|None;created_at:datetime;execution_mode:str="PAPER";live_execution_eligible:bool=False;blockers:tuple[str,...]=();warnings:tuple[str,...]=();schema_version:str="market_candle_series.v1"
 def __post_init__(self):
  if not self.series_id or not isinstance(self.candles,tuple) or not isinstance(self.created_at,datetime) or not self.created_at.tzinfo or self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="market_candle_series.v1":raise ValueError("Invalid candle series.")
  if not self.candles and not self.blockers:raise ValueError("Empty series requires blocker.")
  starts=[c.start_at for c in self.candles]
  if any(not isinstance(c,MarketCandleV1) or (c.underlying_symbol,c.exchange,c.timeframe)!=(self.underlying_symbol,self.exchange,self.timeframe) for c in self.candles) or starts!=sorted(starts) or len(set(starts))!=len(starts) or any(a.end_at>b.start_at for a,b in zip(self.candles,self.candles[1:])):raise ValueError("Invalid candle series candles.")
  if (self.requested_from is None)!=(self.requested_until is None) or (self.requested_from and (not self.requested_from.tzinfo or not self.requested_until.tzinfo or self.requested_from>=self.requested_until)):raise ValueError("Invalid requested range.")
  object.__setattr__(self,"blockers",tuple(self.blockers));object.__setattr__(self,"warnings",tuple(self.warnings))
 def to_dict(self):return {"series_id":self.series_id,"underlying_symbol":self.underlying_symbol,"exchange":self.exchange,"timeframe":self.timeframe,"candles":[c.to_dict() for c in self.candles],"blockers":list(self.blockers),"warnings":list(self.warnings),"schema_version":self.schema_version}
