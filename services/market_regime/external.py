from services.contracts.external_context_regime_component_result_v1 import ExternalContextRegimeComponentResultV1
from services.core.market_identity import normalize_market_identity
def evaluate_external_context_regime_component(*,underlying_symbol,exchange,external_market_context,policy,created_at,result_id):
 i=normalize_market_identity(underlying_symbol,exchange)
 if not i or not result_id:raise ValueError("inputs")
 if external_market_context is None:return ExternalContextRegimeComponentResultV1(result_id,created_at,i[0],i[1],None,"UNAVAILABLE","UNAVAILABLE","UNAVAILABLE","UNAVAILABLE","UNAVAILABLE","UNAVAILABLE",0,0,"UNAVAILABLE")
 d=external_market_context.aggregate_direction
 return ExternalContextRegimeComponentResultV1(result_id,created_at,i[0],i[1],external_market_context,external_market_context.context_status,d,"UNAVAILABLE","UNAVAILABLE",external_market_context.risk_level,external_market_context.entry_restriction_state,external_market_context.aggregate_strength,external_market_context.aggregate_strength,external_market_context.confirmation_state,external_market_context.blockers,external_market_context.warnings)
