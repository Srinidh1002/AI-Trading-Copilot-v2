"""
Trend Engine V2
"""

from typing import Dict


def analyze_trend(snapshot: Dict):

    price = float(snapshot["ltp"])

    ind = snapshot["indicators"]

    ema20 = float(ind["EMA20"])
    ema50 = float(ind["EMA50"])
    ema200 = float(ind["EMA200"])

    rsi = float(ind["RSI"])
    adx = float(ind["ADX"])

    macd = float(ind["MACD"])
    macd_signal = float(ind["MACD_SIGNAL"])

    vwap = float(ind["VWAP"])

    score = 50

    reasons = []

    # =====================================================
    # EMA Structure
    # =====================================================

    if price > ema20 > ema50 > ema200:

        trend = "Bullish"

        score += 20

        reasons.append("Bullish EMA alignment")

    elif price < ema20 < ema50 < ema200:

        trend = "Bearish"

        score -= 20

        reasons.append("Bearish EMA alignment")

    else:

        trend = "Sideways"

        reasons.append("Mixed EMA alignment")

    # =====================================================
    # RSI
    # =====================================================

    if rsi >= 70:

        momentum = "Overbought"

        score -= 5

    elif rsi <= 30:

        momentum = "Oversold"

        score += 5

    elif rsi >= 55:

        momentum = "Bullish"

        score += 10

    elif rsi <= 45:

        momentum = "Bearish"

        score -= 10

    else:

        momentum = "Neutral"

    # =====================================================
    # ADX
    # =====================================================

    if adx >= 40:

        strength = "Very Strong"

        score += 10

    elif adx >= 25:

        strength = "Strong"

        score += 5

    elif adx >= 20:

        strength = "Moderate"

    else:

        strength = "Weak"

        score -= 5

    # =====================================================
    # MACD
    # =====================================================

    if macd > macd_signal:

        score += 10

        reasons.append("MACD Bullish")

    else:

        score -= 10

        reasons.append("MACD Bearish")

    # =====================================================
    # VWAP
    # =====================================================

    if price > vwap:

        score += 5

        reasons.append("Above VWAP")

    else:

        score -= 5

        reasons.append("Below VWAP")

    # =====================================================
    # Clamp
    # =====================================================

    score = max(0, min(100, score))

    # =====================================================
    # Signal
    # =====================================================

    if score >= 70:

        signal = "BUY"

    elif score <= 30:

        signal = "SELL"

    else:

        signal = "HOLD"

    return {

        "signal": signal,

        "score": score,

        "trend": trend,

        "momentum": momentum,

        "strength": strength,

        "confidence": score,

        "reason": " | ".join(reasons),

        "rsi": round(rsi, 2),

        "adx": round(adx, 2),

        "macd": round(macd, 2),

        "macd_signal": round(macd_signal, 2),

        "vwap": round(vwap, 2),

    }