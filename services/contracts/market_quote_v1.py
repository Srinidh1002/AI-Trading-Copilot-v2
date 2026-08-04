from dataclasses import dataclass
from datetime import datetime
import json,math
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES
from services.contracts.market_data_provenance_v1 import MarketDataProvenanceV1
def _num(v,positive=True):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and (v>0 if positive else v>=0)
@dataclass(frozen=True,slots=True)
class MarketQuoteV1:
 quote_id:str;underlying_symbol:str;exchange:str;observed_at:datetime;received_at:datetime;last_price:float;previous_close:float|None;open_price:float|None;high_price:float|None;low_price:float|None;volume:float|None;bid_price:float|None;ask_price:float|None;provenance:MarketDataProvenanceV1;execution_mode:str="PAPER";live_execution_eligible:bool=False;warnings:tuple[str,...]=();schema_version:str="market_quote.v1"
 def __post_init__(self):
  vals=(self.last_price,)+tuple(v for v in (self.previous_close,self.open_price,self.high_price,self.low_price,self.bid_price,self.ask_price) if v is not None)
  if not self.quote_id or (self.underlying_symbol,self.exchange) not in SUPPORTED_MARKET_IDENTITIES or not all(isinstance(v,datetime) and v.tzinfo for v in (self.observed_at,self.received_at)) or not all(_num(v) for v in vals) or (self.volume is not None and not _num(self.volume,False)) or not isinstance(self.provenance,MarketDataProvenanceV1) or self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="market_quote.v1":raise ValueError("Invalid market quote.")
  if self.high_price is not None and self.low_price is not None and (self.high_price<self.low_price or any(v is not None and not self.low_price<=v<=self.high_price for v in (self.open_price,self.last_price))) or (self.bid_price is not None and self.ask_price is not None and self.ask_price<self.bid_price):raise ValueError("Invalid quote range.")
  object.__setattr__(self,"warnings",tuple(self.warnings))
 def to_dict(self):return {n:(getattr(self,n).isoformat() if isinstance(getattr(self,n),datetime) else getattr(self,n).to_dict() if n=="provenance" else list(getattr(self,n)) if n=="warnings" else getattr(self,n)) for n in self.__dataclass_fields__}
