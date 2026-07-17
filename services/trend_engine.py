"""
Trend Engine V0.6
"""


def analyze_trend(snapshot):

    price = snapshot["ltp"]

    indicators = snapshot["indicators"]

    ema20 = indicators["EMA20"]
    ema50 = indicators["EMA50"]
    ema200 = indicators["EMA200"]
    rsi = indicators["RSI"]

    # ==========================================
    # Trend Direction
    # ==========================================

    if price > ema20 > ema50 > ema200:
        trend = "Bullish"

    elif price < ema20 < ema50 < ema200:
        trend = "Bearish"

    else:
        trend = "Sideways"

    # ==========================================
    # Momentum
    # ==========================================

    if rsi >= 70:
        momentum = "Overbought"

    elif rsi <= 30:
        momentum = "Oversold"

    elif rsi >= 55:
        momentum = "Bullish"

    elif rsi <= 45:
        momentum = "Bearish"

    else:
        momentum = "Neutral"

    # ==========================================
    # Trend Strength
    # ==========================================

    distance = abs(price - ema20)

    if distance > 100:
        strength = "Strong"

    elif distance > 40:
        strength = "Moderate"

    else:
        strength = "Weak"

    return {
        "trend": trend,
        "momentum": momentum,
        "strength": strength,
        "rsi": round(rsi, 2),
    }