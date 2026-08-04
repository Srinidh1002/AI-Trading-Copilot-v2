from services.contracts.technical_regime_component_result_v1 import TechnicalRegimeComponentResultV1
from services.contracts.market_regime_policy_v1 import DEFAULT_MARKET_REGIME_POLICY,MarketRegimePolicyV1
from services.contracts.technical_intelligence_result_v1 import TechnicalIntelligenceResultV1
from services.core.market_identity import normalize_market_identity
def evaluate_technical_regime_component(*,underlying_symbol,exchange,technical_context,policy=DEFAULT_MARKET_REGIME_POLICY,created_at,result_id):
 i=normalize_market_identity(underlying_symbol,exchange)
 if not i or not isinstance(policy,MarketRegimePolicyV1) or not result_id:raise ValueError("inputs")
 if technical_context is None:return TechnicalRegimeComponentResultV1(result_id,created_at,i[0],i[1],None,"UNAVAILABLE","UNAVAILABLE","UNAVAILABLE","UNAVAILABLE",0,0,"UNAVAILABLE",0,0)
 if not isinstance(technical_context,TechnicalIntelligenceResultV1):raise TypeError("technical_context")
 d={"BULLISH":"POSITIVE","BEARISH":"NEGATIVE","NEUTRAL":"FLAT","MIXED":"CONFLICTING"}.get(technical_context.aggregate_bias,"UNAVAILABLE");status="READY" if technical_context.status=="READY" else "READY_WITH_WARNINGS";trend="UPTREND" if d=="POSITIVE" else "DOWNTREND" if d=="NEGATIVE" else "SIDEWAYS" if d=="FLAT" else "CONFLICTING" if d=="CONFLICTING" else "UNAVAILABLE"
 return TechnicalRegimeComponentResultV1(result_id,created_at,i[0],i[1],technical_context,status,d,trend,"NORMAL",technical_context.aggregate_strength,technical_context.aggregate_strength,"CONFIRMING" if d in {"POSITIVE","NEGATIVE"} else "NOT_CONFIRMING",technical_context.valid_indicator_count,technical_context.unavailable_indicator_count,technical_context.blockers,technical_context.warnings)
