"""Safe immutable captured live inputs for one certified PAPER market."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

_IDENTITIES={("NIFTY","NSE","99926000","NFO"),("SENSEX","BSE","99919000","BFO")};_TIMEFRAMES=("5m","15m","1h","1d")
def _safe(value:Any)->Any:
 if isinstance(value,Mapping):
  if any(any(word in str(key).lower() for word in ("secret","password","pin","jwt","totp","authorization")) for key in value):raise ValueError("unsafe captured field")
  return MappingProxyType({str(key):_safe(item) for key,item in value.items()})
 if isinstance(value,(tuple,list)):return tuple(_safe(item) for item in value)
 if value is None or isinstance(value,(str,bool,int,float,datetime)):return value
 raise TypeError("unsafe captured value")
@dataclass(frozen=True,slots=True)
class CertifiedLiveCapturedEvidenceV1:
 underlying_symbol:str;spot_exchange:str;spot_token:str;option_exchange:str;spot_payload:Mapping[str,Any];candle_rows_by_timeframe:Mapping[str,tuple[tuple[Any,...],...]];option_contracts:tuple[Mapping[str,Any],...];provider_timestamp:datetime;evaluated_at:datetime;provider_blockers:tuple[str,...]=();provider_warnings:tuple[str,...]=();cache_metadata:Mapping[str,Any]=field(default_factory=dict);schema_version:str="certified_live_captured_evidence.v1"
 def __post_init__(self):
  if (self.underlying_symbol,self.spot_exchange,self.spot_token,self.option_exchange) not in _IDENTITIES:raise ValueError("identity")
  if any(not isinstance(item,datetime) or item.tzinfo is None or item.utcoffset() is None for item in (self.provider_timestamp,self.evaluated_at)):raise ValueError("timestamps")
  rows=dict(self.candle_rows_by_timeframe)
  if tuple(rows)!=tuple(item for item in _TIMEFRAMES if item in rows):raise ValueError("timeframe order")
  object.__setattr__(self,"spot_payload",_safe(self.spot_payload));object.__setattr__(self,"candle_rows_by_timeframe",MappingProxyType({key:tuple(tuple(row) for row in value) for key,value in rows.items()}));object.__setattr__(self,"option_contracts",tuple(_safe(item) for item in self.option_contracts));object.__setattr__(self,"cache_metadata",_safe(self.cache_metadata))
 def to_dict(self):return {"underlying_symbol":self.underlying_symbol,"spot_exchange":self.spot_exchange,"spot_token":self.spot_token,"option_exchange":self.option_exchange,"candle_timeframes":list(self.candle_rows_by_timeframe),"option_contract_count":len(self.option_contracts),"provider_timestamp":self.provider_timestamp.isoformat(),"evaluated_at":self.evaluated_at.isoformat(),"provider_blockers":list(self.provider_blockers),"provider_warnings":list(self.provider_warnings),"cache_metadata":dict(self.cache_metadata),"schema_version":self.schema_version}
