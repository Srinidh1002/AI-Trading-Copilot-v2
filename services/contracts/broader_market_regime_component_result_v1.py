from dataclasses import dataclass
from datetime import datetime
from services.contracts.broader_market_intelligence_result_v1 import BroaderMarketIntelligenceResultV1
from services.core.market_identity import normalize_market_identity
@dataclass(frozen=True,slots=True)
class BroaderMarketRegimeComponentResultV1:
 broader_market_regime_component_result_id:str;created_at:datetime;underlying_symbol:str;exchange:str;broader_market_context:BroaderMarketIntelligenceResultV1|None;context_status:str;directional_state:str;breadth_state:str;correlation_state:str;volatility_state:str;component_strength:float;confidence:float;confirmation_state:str;available_signal_count:int;unavailable_signal_count:int;blockers:tuple[str,...]=();warnings:tuple[str,...]=();execution_mode:str="PAPER";live_execution_eligible:bool=False
 def __post_init__(self):
  i=normalize_market_identity(self.underlying_symbol,self.exchange)
  if not i or not isinstance(self.created_at,datetime) or self.created_at.tzinfo is None:raise ValueError("identity/time")
  if self.broader_market_context and (not isinstance(self.broader_market_context,BroaderMarketIntelligenceResultV1) or (self.broader_market_context.underlying_symbol,self.broader_market_context.exchange)!=i):raise ValueError("context")
