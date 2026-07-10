"""
Live Indian Market Indices
"""

import yfinance as yf


def _get_index(symbol):
    """
    Returns price and change for a market index.
    """

    try:

        ticker = yf.Ticker(symbol)

        info = ticker.info

        price = info.get(
            "regularMarketPrice",
            0
        )

        previous = info.get(
            "regularMarketPreviousClose",
            price
        )

        change = round(
            price - previous,
            2
        )

        return {
            "price": price,
            "change": change
        }

    except Exception:

        return {
            "price": 0,
            "change": 0
        }


def market_indices():
    """
    Returns all Indian market indices.
    """

    return {

        "nifty": _get_index("^NSEI"),

        "banknifty": _get_index("^NSEBANK"),

        "sensex": _get_index("^BSESN"),

        "vix": _get_index("^INDIAVIX")

    }