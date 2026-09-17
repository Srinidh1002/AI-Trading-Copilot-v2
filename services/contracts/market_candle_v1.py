from dataclasses import dataclass
from datetime import datetime
import json,math
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES
from services.contracts.market_data_provenance_v1 import MarketDataProvenanceV1
_TF=("1m","3m","5m","15m","30m","1h","1d")
@dataclass(frozen=True,slots=True)
class MarketCandleV1:
 candle_id:str;underlying_symbol:str;exchange:str;timeframe:str;start_at:datetime;end_at:datetime;open_price:float;high_price:float;low_price:float;close_price:float;volume:float;is_complete:bool;provenance:MarketDataProvenanceV1;warnings:tuple[str,...]=();schema_version:str="market_candle.v1"
 def __post_init__(self):
  vals=(self.open_price,self.high_price,self.low_price,self.close_price)
  if not self.candle_id or (self.underlying_symbol,self.exchange) not in SUPPORTED_MARKET_IDENTITIES or self.timeframe not in _TF or not all(isinstance(v,datetime) and v.tzinfo for v in (self.start_at,self.end_at)) or self.end_at<=self.start_at or not all(isinstance(v,(int,float)) and math.isfinite(v) and v>0 for v in vals) or not isinstance(self.volume,(int,float)) or not math.isfinite(self.volume) or self.volume<0 or self.high_price<max(self.open_price,self.close_price,self.low_price) or self.low_price>min(self.open_price,self.close_price,self.high_price) or not isinstance(self.provenance,MarketDataProvenanceV1) or self.schema_version!="market_candle.v1":raise ValueError("Invalid market candle.")
  object.__setattr__(self,"warnings",tuple(self.warnings))
 def to_dict(self):return {n:(getattr(self,n).isoformat() if isinstance(getattr(self,n),datetime) else getattr(self,n).to_dict() if n=="provenance" else list(getattr(self,n)) if n=="warnings" else getattr(self,n)) for n in self.__dataclass_fields__}
