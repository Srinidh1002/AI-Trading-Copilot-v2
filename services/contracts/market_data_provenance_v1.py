from dataclasses import dataclass
from datetime import datetime
import json,math
@dataclass(frozen=True,slots=True)
class MarketDataProvenanceV1:
 provider:str;provider_symbol:str|None;provider_exchange:str|None;source_type:str;fetched_at:datetime;received_at:datetime;is_cached:bool;cache_age_seconds:float|None;provider_request_id:str|None;warnings:tuple[str,...]=();schema_version:str="market_data_provenance.v1"
 def __post_init__(self):
  if not isinstance(self.provider,str) or not self.provider.strip() or self.source_type not in {"LIVE","CACHE","REPLAY","TEST"} or self.schema_version!="market_data_provenance.v1" or not all(isinstance(v,datetime) and v.tzinfo for v in (self.fetched_at,self.received_at)) or self.received_at<self.fetched_at or (not self.is_cached and self.cache_age_seconds is not None) or (self.is_cached and (not isinstance(self.cache_age_seconds,(int,float)) or self.cache_age_seconds<0)):raise ValueError("Invalid data provenance.")
  object.__setattr__(self,"provider",self.provider.strip().upper());object.__setattr__(self,"warnings",tuple(self.warnings))
 def to_dict(self):return {n:(getattr(self,n).isoformat() if isinstance(getattr(self,n),datetime) else list(getattr(self,n)) if n=="warnings" else getattr(self,n)) for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"))
