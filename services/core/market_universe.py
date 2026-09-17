"""Static provider-neutral Phase-One market universe; no I/O or clients."""
from services.contracts.market_instrument_v1 import MarketInstrumentV1
from services.contracts.market_universe_v1 import MarketUniverseV1
from services.core.market_identity import normalize_market_identity, normalize_market_symbol
CANONICAL_MARKET_INSTRUMENTS=(
 MarketInstrumentV1("NIFTY","NSE","NIFTY 50","INDEX","INR","Asia/Kolkata",("NIFTY50","NIFTY 50"),1,True),
 MarketInstrumentV1("BANKNIFTY","NSE","NIFTY BANK","INDEX","INR","Asia/Kolkata",("BANK NIFTY","NIFTY BANK"),2,True),
 MarketInstrumentV1("FINNIFTY","NSE","NIFTY FINANCIAL SERVICES","INDEX","INR","Asia/Kolkata",("FIN NIFTY","NIFTY FINANCIAL SERVICES"),3,True),
 MarketInstrumentV1("SENSEX","BSE","BSE SENSEX","INDEX","INR","Asia/Kolkata",("BSE SENSEX",),4,True),
)
CANONICAL_MARKET_UNIVERSE=MarketUniverseV1("INDIA_INDEX_PHASE_ONE",CANONICAL_MARKET_INSTRUMENTS)
CANONICAL_MARKET_IDENTITIES=tuple((v.underlying_symbol,v.exchange) for v in CANONICAL_MARKET_INSTRUMENTS)
CANONICAL_MARKET_SYMBOLS=tuple(v.underlying_symbol for v in CANONICAL_MARKET_INSTRUMENTS)
def resolve_market_alias(value):
 result=normalize_market_symbol(value)
 if result is None:raise ValueError("Unsupported market symbol.")
 return result
def resolve_market_identity(underlying_symbol,exchange=None):
 result=normalize_market_identity(underlying_symbol,exchange)
 if result is None:raise ValueError("Unsupported market identity.")
 return result
def get_market_instrument(underlying_symbol,exchange=None):
 symbol,actual=resolve_market_identity(underlying_symbol,exchange)
 return next(v for v in CANONICAL_MARKET_INSTRUMENTS if (v.underlying_symbol,v.exchange)==(symbol,actual))
def list_market_instruments():return CANONICAL_MARKET_INSTRUMENTS
def is_canonical_market_identity(underlying_symbol,exchange):
 try:return resolve_market_identity(underlying_symbol,exchange) in CANONICAL_MARKET_IDENTITIES
 except ValueError:return False
