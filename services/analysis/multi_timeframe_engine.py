"""
Multi Timeframe Engine V1
"""


def analyze_multi_timeframe(snapshot):

    history = snapshot["history"]

    # Normalize column names to lowercase

    close = history["close"]

    ema20 = close.ewm(span=20).mean().iloc[-1]
    ema50 = close.ewm(span=50).mean().iloc[-1]

    current = close.iloc[-1]

    if current > ema20 > ema50:
        trend = "Bullish"

    elif current < ema20 < ema50:
        trend = "Bearish"

    else:
        trend = "Sideways"

    return {
        "timeframe": "5 Minute",
        "price": round(current, 2),
        "ema20": round(ema20, 2),
        "ema50": round(ema50, 2),
        "trend": trend,
    }