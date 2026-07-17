"""
Trend Engine V1
"""

def analyze_trend(technical):

    ema20 = technical["EMA20"]
    ema50 = technical["EMA50"]
    ema200 = technical["EMA200"]

    rsi = technical["RSI"]
    adx = technical["ADX"]

    # ----------------------------------
    # Trend
    # ----------------------------------

    if ema20 > ema50 > ema200:
        trend = "Bullish"

    elif ema20 < ema50 < ema200:
        trend = "Bearish"

    else:
        trend = "Sideways"

    # ----------------------------------
    # Bias
    # ----------------------------------

    if trend == "Bullish" and rsi > 55:
        bias = "BUY"

    elif trend == "Bearish" and rsi < 45:
        bias = "SELL"

    else:
        bias = "WAIT"

    # ----------------------------------
    # Strength
    # ----------------------------------

    if adx >= 30:
        strength = "Strong"

    elif adx >= 20:
        strength = "Moderate"

    else:
        strength = "Weak"

    return {
        "trend": trend,
        "bias": bias,
        "strength": strength,
    }