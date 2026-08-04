"""Immutable canonical identity registry for supported index F&O markets."""
from __future__ import annotations

SUPPORTED_MARKET_IDENTITIES = (
    ("NIFTY", "NSE"),
    ("BANKNIFTY", "NSE"),
    ("FINNIFTY", "NSE"),
    ("SENSEX", "BSE"),
)
SUPPORTED_MARKET_SYMBOLS = tuple(symbol for symbol, _ in SUPPORTED_MARKET_IDENTITIES)
_EXCHANGES = dict(SUPPORTED_MARKET_IDENTITIES)
_ALIASES = {
    "NIFTY": "NIFTY", "NIFTY50": "NIFTY", "NIFTY 50": "NIFTY",
    "BANKNIFTY": "BANKNIFTY", "BANK NIFTY": "BANKNIFTY", "NIFTY BANK": "BANKNIFTY",
    "FINNIFTY": "FINNIFTY", "FIN NIFTY": "FINNIFTY", "NIFTY FINANCIAL SERVICES": "FINNIFTY",
    "SENSEX": "SENSEX", "BSE SENSEX": "SENSEX",
}

def _normalise(value: object) -> str | None:
    if not isinstance(value, str): return None
    value = " ".join(value.upper().split())
    return value or None

def normalize_market_symbol(value: object) -> str | None:
    """Return a canonical supported symbol, or ``None`` for unsupported input."""
    value = _normalise(value)
    return _ALIASES.get(value) if value else None

def expected_exchange_for_symbol(symbol: object) -> str | None:
    canonical = normalize_market_symbol(symbol)
    return _EXCHANGES.get(canonical) if canonical else None

def normalize_market_identity(symbol: object, exchange: object = None) -> tuple[str, str] | None:
    canonical = normalize_market_symbol(symbol)
    expected = _EXCHANGES.get(canonical) if canonical else None
    if not expected: return None
    if exchange is None: return canonical, expected
    actual = _normalise(exchange)
    return (canonical, expected) if actual == expected else None

def is_supported_market_identity(symbol: object, exchange: object) -> bool:
    return normalize_market_identity(symbol, exchange) is not None
