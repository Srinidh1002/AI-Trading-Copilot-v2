from dataclasses import dataclass
from datetime import datetime
from services.contracts.external_market_context_result_v1 import ExternalMarketContextResultV1
from services.core.market_identity import normalize_market_identity
@dataclass(frozen=True,slots=True)
class ExternalContextRegimeComponentResultV1:
 external_context_regime_component_result_id:str;created_at:datetime;underlying_symbol:str;exchange:str;external_market_context:ExternalMarketContextResultV1|None;context_status:str;directional_state:str;global_state:str;institutional_state:str;event_risk_state:str;entry_restriction_state:str;component_strength:float;confidence:float;confirmation_state:str;blockers:tuple[str,...]=();warnings:tuple[str,...]=()
 def __post_init__(self):
  i=normalize_market_identity(self.underlying_symbol,self.exchange)
  if not i or not isinstance(self.created_at,datetime) or self.created_at.tzinfo is None:raise ValueError("identity/time")
  if self.external_market_context and (not isinstance(self.external_market_context,ExternalMarketContextResultV1) or (self.external_market_context.underlying_symbol,self.external_market_context.exchange)!=i):raise ValueError("context")
