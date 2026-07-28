from __future__ import annotations
import json
from dataclasses import dataclass
from services.contracts.market_instrument_v1 import MarketInstrumentV1
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES
@dataclass(frozen=True,slots=True)
class MarketUniverseV1:
 universe_name:str;instruments:tuple[MarketInstrumentV1,...];execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="market_universe.v1"
 def __post_init__(self):
  if self.universe_name!="INDIA_INDEX_PHASE_ONE" or not isinstance(self.instruments,tuple) or len(self.instruments)!=4 or self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="market_universe.v1":raise ValueError("Invalid market universe controls.")
  if tuple((v.underlying_symbol,v.exchange) for v in self.instruments)!=SUPPORTED_MARKET_IDENTITIES or len({a for v in self.instruments for a in v.aliases})!=sum(len(v.aliases) for v in self.instruments):raise ValueError("Invalid market universe instruments.")
 def to_dict(self):return {"universe_name":self.universe_name,"instruments":[v.to_dict() for v in self.instruments],"execution_mode":self.execution_mode,"live_execution_eligible":False,"schema_version":self.schema_version}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"))
