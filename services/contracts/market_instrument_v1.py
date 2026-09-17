from __future__ import annotations
import json
from dataclasses import dataclass
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES, normalize_market_symbol
_POSITIONS={"NIFTY":1,"BANKNIFTY":2,"FINNIFTY":3,"SENSEX":4}
@dataclass(frozen=True,slots=True)
class MarketInstrumentV1:
 underlying_symbol:str;exchange:str;display_name:str;instrument_type:str;currency:str;timezone:str;aliases:tuple[str,...];universe_position:int;enabled:bool;schema_version:str="market_instrument.v1"
 def __post_init__(self):
  if (self.underlying_symbol,self.exchange) not in SUPPORTED_MARKET_IDENTITIES or self.instrument_type!="INDEX" or self.currency!="INR" or self.timezone!="Asia/Kolkata" or self.enabled is not True or self.schema_version!="market_instrument.v1" or self.universe_position!=_POSITIONS.get(self.underlying_symbol):raise ValueError("Invalid canonical market instrument.")
  if not isinstance(self.display_name,str) or not self.display_name.strip() or not isinstance(self.aliases,tuple):raise ValueError("Invalid market instrument metadata.")
  aliases=tuple(" ".join(a.upper().split()) if isinstance(a,str) else "" for a in self.aliases)
  if not aliases or any(not a for a in aliases) or len(set(aliases))!=len(aliases) or self.underlying_symbol in aliases:raise ValueError("Invalid market aliases.")
  object.__setattr__(self,"aliases",aliases)
 def to_dict(self):return {n:list(getattr(self,n)) if n=="aliases" else getattr(self,n) for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"))
