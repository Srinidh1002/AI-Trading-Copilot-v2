"""
Candlestick Pattern Engine V2
"""

from typing import Dict
import pandas as pd


def detect_pattern(df: pd.DataFrame) -> Dict:

    if len(df) < 3:
        return {
            "pattern": "Unknown",
            "signal": "HOLD",
            "score": 50,
            "confidence": 50,
            "reason": "Not enough candles"
        }

    df = df.copy()
    df.columns = [c.lower() for c in df.columns]

    current = df.iloc[-1]
    previous = df.iloc[-2]

    o = float(current["open"])
    h = float(current["high"])
    l = float(current["low"])
    c = float(current["close"])

    po = float(previous["open"])
    pc = float(previous["close"])

    body = abs(c - o)
    candle_range = max(h - l, 0.00001)

    upper = h - max(o, c)
    lower = min(o, c) - l

    score = 50
    pattern = "None"
    signal = "HOLD"
    confidence = 50
    reason = "No major pattern"

    # =========================================================
    # Doji
    # =========================================================

    if body <= candle_range * 0.10:

        pattern = "Doji"
        signal = "HOLD"
        score = 50
        confidence = 55
        reason = "Market indecision"

    # =========================================================
    # Hammer
    # =========================================================

    elif lower >= body * 2 and upper <= body:

        pattern = "Hammer"
        signal = "BUY"
        score = 80
        confidence = 80
        reason = "Bullish reversal"

    # =========================================================
    # Shooting Star
    # =========================================================

    elif upper >= body * 2 and lower <= body:

        pattern = "Shooting Star"
        signal = "SELL"
        score = 20
        confidence = 80
        reason = "Bearish reversal"

    # =========================================================
    # Bullish Engulfing
    # =========================================================

    elif (

        pc < po and

        c > o and

        o < pc and

        c > po

    ):

        pattern = "Bullish Engulfing"
        signal = "BUY"
        score = 90
        confidence = 90
        reason = "Strong bullish reversal"

    # =========================================================
    # Bearish Engulfing
    # =========================================================

    elif (

        pc > po and

        c < o and

        o > pc and

        c < po

    ):

        pattern = "Bearish Engulfing"
        signal = "SELL"
        score = 10
        confidence = 90
        reason = "Strong bearish reversal"

    # =========================================================
    # Marubozu Bullish
    # =========================================================

    elif c > o and upper < body * 0.10 and lower < body * 0.10:

        pattern = "Bullish Marubozu"
        signal = "BUY"
        score = 85
        confidence = 85
        reason = "Strong bullish momentum"

    # =========================================================
    # Marubozu Bearish
    # =========================================================

    elif c < o and upper < body * 0.10 and lower < body * 0.10:

        pattern = "Bearish Marubozu"
        signal = "SELL"
        score = 15
        confidence = 85
        reason = "Strong bearish momentum"

    # =========================================================
    # Bullish Candle
    # =========================================================

    elif c > o:

        pattern = "Bullish Candle"
        signal = "BUY"
        score = 65
        confidence = 65
        reason = "Bullish close"

    # =========================================================
    # Bearish Candle
    # =========================================================

    else:

        pattern = "Bearish Candle"
        signal = "SELL"
        score = 35
        confidence = 65
        reason = "Bearish close"

    return {

        "pattern": pattern,

        "signal": signal,

        "score": score,

        "confidence": confidence,

        "reason": reason,

        "body": round(body, 2),

        "upper_wick": round(upper, 2),

        "lower_wick": round(lower, 2),

        "open": round(o, 2),

        "high": round(h, 2),

        "low": round(l, 2),

        "close": round(c, 2)

    }