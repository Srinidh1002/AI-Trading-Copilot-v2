"""
Technical AI Score Engine
"""

from services.market_snapshot import get_market_snapshot


def technical_score():

    snapshot = get_market_snapshot()

    indicators = snapshot["indicators"]

    bull = 0
    bear = 0
    reasons = []

    # EMA
    if indicators["EMA20"] > indicators["EMA50"] > indicators["EMA200"]:
        bull += 30
        reasons.append("EMA Bullish")

    elif indicators["EMA20"] < indicators["EMA50"] < indicators["EMA200"]:
        bear += 30
        reasons.append("EMA Bearish")

    # RSI
    rsi = indicators.get("RSI")

    if rsi is not None:

        if rsi >= 60:
            bull += 20
            reasons.append("Strong RSI")

        elif rsi <= 40:
            bear += 20
            reasons.append("Weak RSI")

    # ADX
    adx = indicators.get("ADX")

    if adx is not None and adx >= 25:

        if bull > bear:
            bull += 20
            reasons.append("Strong Trend")

        elif bear > bull:
            bear += 20
            reasons.append("Strong Down Trend")

    # MACD
    macd = indicators.get("MACD")
    signal = indicators.get("MACD_SIGNAL")

    if macd is not None and signal is not None:

        if macd > signal:
            bull += 20
            reasons.append("MACD Bullish")

        else:
            bear += 20
            reasons.append("MACD Bearish")

    # VWAP
    price = indicators.get("CURRENT_PRICE")
    vwap = indicators.get("VWAP")

    if (
        price is not None
        and vwap is not None
    ):

        if price > vwap:
            bull += 10
            reasons.append("Above VWAP")

        else:
            bear += 10
            reasons.append("Below VWAP")

    else:

        reasons.append("VWAP Unavailable")

    return {

        "bull_score": bull,

        "bear_score": bear,

        "reasons": reasons,

        "snapshot": snapshot,

        "indicators": indicators,

    }