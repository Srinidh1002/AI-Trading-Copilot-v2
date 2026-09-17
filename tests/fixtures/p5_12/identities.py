from types import MappingProxyType
from services.core.market_identity import normalize_market_identity

CANONICAL_MARKET_IDENTITIES=(('NIFTY','NSE'),('BANKNIFTY','NSE'),('FINNIFTY','NSE'),('SENSEX','BSE'))
CANONICAL_MARKET_ORDER=MappingProxyType({identity:index for index,identity in enumerate(CANONICAL_MARKET_IDENTITIES)})
def normalize_test_identity(symbol,exchange):
 identity=normalize_market_identity(symbol,exchange)
 if identity not in CANONICAL_MARKET_IDENTITIES:raise ValueError('unsupported identity')
 return identity
