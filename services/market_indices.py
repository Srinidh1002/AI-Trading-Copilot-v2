"""
Live Indian Market Indices
"""

import yfinance as yf

_SYMBOLS = {
    "nifty": "^NSEI",
    "banknifty": "^NSEBANK",
    "sensex": "^BSESN",
    "vix": "^INDIAVIX",
}


def _get_index(symbol):
    """
    Returns price and change for a market index.
    """

    try:
        ticker = yf.Ticker(symbol)

        info = ticker.fast_info

        price = info.get("lastPrice", 0)

        previous = info.get("previousClose", price)

        change = round(
            price - previous,
            2,
        )

        return {
            "price": price,
            "change": change,
        }

    except Exception:
        return {
            "price": 0,
            "change": 0,
        }


def market_indices():
    """
    Returns all Indian market indices.
    """

    return {
        name: _get_index(symbol)
        for name, symbol in _SYMBOLS.items()
    }