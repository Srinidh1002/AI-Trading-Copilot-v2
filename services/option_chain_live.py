"""
Live NSE Option Chain
"""

from services.nse_client import NSEClient


_client = None


def _get_client():
    global _client

    if _client is None:
        _client = NSEClient()

    return _client


def get_option_chain(symbol="NIFTY"):

    return _get_client().option_chain(symbol)