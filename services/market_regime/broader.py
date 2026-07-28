from services.contracts.broader_market_regime_component_result_v1 import BroaderMarketRegimeComponentResultV1
from services.core.market_identity import normalize_market_identity
def evaluate_broader_market_regime_component(*,underlying_symbol,exchange,broader_market_context,policy,created_at,result_id):
 i=normalize_market_identity(underlying_symbol,exchange)
 if not i or not result_id:raise ValueError("inputs")
 if broader_market_context is None:return BroaderMarketRegimeComponentResultV1(result_id,created_at,i[0],i[1],None,"UNAVAILABLE","UNAVAILABLE","UNAVAILABLE","UNAVAILABLE","UNAVAILABLE",0,0,"UNAVAILABLE",0,0)
 d={"BULLISH":"POSITIVE","BEARISH":"NEGATIVE","NEUTRAL":"FLAT","CONFLICTING":"CONFLICTING"}.get(broader_market_context.aggregate_bias,"UNAVAILABLE")
 return BroaderMarketRegimeComponentResultV1(result_id,created_at,i[0],i[1],broader_market_context,"READY" if broader_market_context.intelligence_status=="READY" else "READY_WITH_WARNINGS",d,"UNAVAILABLE","CONFIRMING" if broader_market_context.confirmation_state=="CONFIRMING" else "MIXED","NORMAL",broader_market_context.aggregate_strength,broader_market_context.aggregate_strength,broader_market_context.confirmation_state,broader_market_context.available_component_count,broader_market_context.unavailable_component_count,broader_market_context.blockers,broader_market_context.warnings)
