from __future__ import annotations
import json
from dataclasses import dataclass
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES
@dataclass(frozen=True,slots=True)
class ProviderMarketMappingV1:
 provider:str;underlying_symbol:str;exchange:str;mapping_status:str;provider_symbol:str|None;provider_exchange:str|None;source_classification:str;warnings:tuple[str,...]=();schema_version:str="provider_market_mapping.v1"
 def __post_init__(self):
  if self.provider not in {"YFINANCE","ANGEL_SMARTAPI","NSE_OPTION_CHAIN"} or (self.underlying_symbol,self.exchange) not in SUPPORTED_MARKET_IDENTITIES or self.mapping_status not in {"SUPPORTED","UNSUPPORTED","UNKNOWN"} or self.source_classification not in {"EXISTING_RUNTIME","EXISTING_TEST","AUDIT_CONFIRMED"} or self.schema_version!="provider_market_mapping.v1":raise ValueError("Invalid provider market mapping.")
  warnings=tuple(self.warnings)
  if any(not isinstance(w,str) or not w for w in warnings):raise ValueError("Invalid mapping warnings.")
  if self.mapping_status=="SUPPORTED":
   if not isinstance(self.provider_symbol,str) or not self.provider_symbol or not isinstance(self.provider_exchange,str) or not self.provider_exchange or warnings:raise ValueError("Supported mapping requires proven provider identity.")
  elif self.provider_symbol is not None or self.provider_exchange is not None or not warnings:raise ValueError("Unknown or unsupported mapping requires bounded warning.")
  object.__setattr__(self,"warnings",warnings)
 def to_dict(self):return {n:list(getattr(self,n)) if n=="warnings" else getattr(self,n) for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"))
