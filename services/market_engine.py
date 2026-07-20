"""
Market AI Score Engine
"""

import yfinance as yf


def market_score():

    bull = 0
    bear = 0
    reasons = []

    try:

        nifty = yf.Ticker("^NSEI")

        info = nifty.fast_info

        previous = info.get("previous_close")
        current = info.get("last_price")

        if previous is not None and current is not None:

            if current > previous:

                bull += 30
                reasons.append("NIFTY Green")

            else:

                bear += 30
                reasons.append("NIFTY Red")

        else:

            reasons.append("Market Data Unavailable")

    except Exception:

        reasons.append("Market Data Unavailable")

    return {

        "bull_score": bull,

        "bear_score": bear,

        "reasons": reasons,

    }