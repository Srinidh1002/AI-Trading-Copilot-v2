def get_market_snapshot(*args, **kwargs):
    """Lazily preserve the historical core snapshot public API."""
    from .market_snapshot import get_market_snapshot as _get_market_snapshot
    return _get_market_snapshot(*args, **kwargs)
from .market_identity import (
    SUPPORTED_MARKET_IDENTITIES, SUPPORTED_MARKET_SYMBOLS,
    expected_exchange_for_symbol, is_supported_market_identity,
    normalize_market_identity, normalize_market_symbol,
)
