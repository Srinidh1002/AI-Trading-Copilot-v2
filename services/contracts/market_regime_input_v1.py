from __future__ import annotations
import json
from dataclasses import dataclass,field
from datetime import datetime
from types import MappingProxyType
from typing import Mapping,Any
from services.core.market_identity import normalize_market_identity
from .technical_intelligence_result_v1 import TechnicalIntelligenceResultV1
from .broader_market_intelligence_result_v1 import BroaderMarketIntelligenceResultV1
from .external_market_context_result_v1 import ExternalMarketContextResultV1
from .market_session_validation_v1 import MarketSessionValidationV1
from .technical_regime_component_result_v1 import TechnicalRegimeComponentResultV1
from .broader_market_regime_component_result_v1 import BroaderMarketRegimeComponentResultV1
from .external_context_regime_component_result_v1 import ExternalContextRegimeComponentResultV1
@dataclass(frozen=True,slots=True)
class MarketRegimeInputV1:
 market_regime_input_id:str;created_at:datetime;underlying_symbol:str;exchange:str;technical_intelligence:TechnicalIntelligenceResultV1|None=None;broader_market_intelligence:BroaderMarketIntelligenceResultV1|None=None;external_market_context:ExternalMarketContextResultV1|None=None;market_session_validation:MarketSessionValidationV1|None=None;technical_regime_component:TechnicalRegimeComponentResultV1|None=None;broader_market_regime_component:BroaderMarketRegimeComponentResultV1|None=None;external_context_regime_component:ExternalContextRegimeComponentResultV1|None=None;source_timestamps:Mapping[str,datetime]=field(default_factory=dict);warnings:tuple[str,...]=();blockers:tuple[str,...]=();metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="market_regime_input.v1"
 def __post_init__(self):
  i=normalize_market_identity(self.underlying_symbol,self.exchange)
  if not isinstance(self.market_regime_input_id,str) or not self.market_regime_input_id.strip() or not i or not isinstance(self.created_at,datetime) or self.created_at.tzinfo is None:raise ValueError("invalid regime input")
  object.__setattr__(self,"underlying_symbol",i[0]);object.__setattr__(self,"exchange",i[1])
  for n,t in (("technical_intelligence",TechnicalIntelligenceResultV1),("broader_market_intelligence",BroaderMarketIntelligenceResultV1),("external_market_context",ExternalMarketContextResultV1),("market_session_validation",MarketSessionValidationV1),("technical_regime_component",TechnicalRegimeComponentResultV1),("broader_market_regime_component",BroaderMarketRegimeComponentResultV1),("external_context_regime_component",ExternalContextRegimeComponentResultV1)):
   v=getattr(self,n)
   if v is not None and type(v) is not t:raise TypeError(n)
   if v is not None and ((getattr(v,"underlying_symbol",getattr(v,"symbol",None)),getattr(v,"exchange",None))!=i):raise ValueError("child identity mismatch")
  s={k:v for k,v in self.source_timestamps.items()}
  if any(not isinstance(k,str) or not k.strip() or not isinstance(v,datetime) or v.tzinfo is None for k,v in s.items()):raise ValueError("timestamps")
  object.__setattr__(self,"source_timestamps",MappingProxyType(dict(sorted(s.items()))));object.__setattr__(self,"warnings",tuple(self.warnings));object.__setattr__(self,"blockers",tuple(self.blockers));object.__setattr__(self,"metadata",MappingProxyType(json.loads(json.dumps(dict(self.metadata),sort_keys=True,allow_nan=False))))
  if self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="market_regime_input.v1":raise ValueError("paper")
 def to_dict(self):
  d={n:getattr(self,n) for n in self.__dataclass_fields__}
  d["created_at"]=self.created_at.isoformat()
  for n in ("technical_intelligence","broader_market_intelligence","external_market_context","market_session_validation","technical_regime_component","broader_market_regime_component","external_context_regime_component"):
   value=getattr(self,n);d[n]=value.to_dict() if value is not None and hasattr(value,"to_dict") else None
  d["source_timestamps"]={k:v.isoformat() for k,v in self.source_timestamps.items()};d["warnings"]=list(self.warnings);d["blockers"]=list(self.blockers);d["metadata"]=dict(self.metadata);return d
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
 def semantic_dict(self):
  d=self.to_dict();d.pop("market_regime_input_id");d.pop("created_at");return d
