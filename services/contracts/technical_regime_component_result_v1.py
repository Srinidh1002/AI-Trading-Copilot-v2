from dataclasses import dataclass
from datetime import datetime
from services.contracts.technical_intelligence_result_v1 import TechnicalIntelligenceResultV1
from services.core.market_identity import normalize_market_identity
@dataclass(frozen=True,slots=True)
class TechnicalRegimeComponentResultV1:
 technical_regime_component_result_id:str;created_at:datetime;underlying_symbol:str;exchange:str;technical_context:TechnicalIntelligenceResultV1|None;context_status:str;directional_state:str;trend_state:str;volatility_state:str;component_strength:float;confidence:float;confirmation_state:str;available_signal_count:int;unavailable_signal_count:int;blockers:tuple[str,...]=();warnings:tuple[str,...]=();schema_version:str="technical_regime_component_result.v1";execution_mode:str="PAPER";live_execution_eligible:bool=False
 def __post_init__(self):
  i=normalize_market_identity(self.underlying_symbol,self.exchange)
  if not i or not isinstance(self.created_at,datetime) or self.created_at.tzinfo is None:raise ValueError("identity/time")
  object.__setattr__(self,"underlying_symbol",i[0]);object.__setattr__(self,"exchange",i[1])
  if self.technical_context and (not isinstance(self.technical_context,TechnicalIntelligenceResultV1) or (self.technical_context.underlying_symbol,self.technical_context.exchange)!=i):raise ValueError("context")
  if self.execution_mode!="PAPER" or self.live_execution_eligible is not False:raise ValueError("paper")
