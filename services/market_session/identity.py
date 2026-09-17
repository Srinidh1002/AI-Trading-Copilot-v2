from dataclasses import dataclass
from services.core.market_identity import normalize_market_identity as _normalize_market_identity
@dataclass(frozen=True,slots=True)
class MarketIdentity: canonical_symbol:str; exchange:str; timezone:str="Asia/Kolkata"
def normalize_market_identity(symbol:str,exchange:str)->MarketIdentity|None:
    value=_normalize_market_identity(symbol,exchange)
    return MarketIdentity(*value) if value else None
