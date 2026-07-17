"""
Indian Market Overview
"""

import yfinance as yf


def get_index(symbol):

    try:

        ticker = yf.Ticker(symbol)

        info = ticker.fast_info

        history = ticker.history(period="2d")

        last = float(info["lastPrice"])

        prev = float(history["Close"].iloc[-2])

        change = round(last - prev, 2)

        percent = round((change / prev) * 100, 2)

        return {
            "price": round(last, 2),
            "change": change,
            "percent": percent,
        }

    except Exception:

        return {
            "price": 0,
            "change": 0,
            "percent": 0,
        }


def market_overview():

    return {

    "NIFTY": get_index("^NSEI"),

    "BANKNIFTY": get_index("^NSEBANK"),

    "SENSEX": get_index("^BSESN"),

    "VIX": get_index("^INDIAVIX"),
}