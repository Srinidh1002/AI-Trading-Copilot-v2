"""
Shared Angel Market Data Client

Provides a lazily initialized singleton instance of
AngelMarketDataClient.
"""

from services.broker.angel_client import AngelMarketDataClient

_market_client = None


def get_market_client():
    global _market_client

    if _market_client is None:
        _market_client = AngelMarketDataClient()

    return _market_client