print("🔥 SUPPORT ENGINE V2 LOADED 🔥")

"""
Support & Resistance Engine V2
"""
"""
Support & Resistance Engine V2
"""

from typing import Dict
import pandas as pd


def calculate_support_resistance(df: pd.DataFrame) -> Dict:

    if len(df) < 20:
        raise ValueError("Minimum 20 candles required.")

    data = df.copy()
    data.columns = [c.lower() for c in data.columns]

    recent = data.tail(20)

    current = float(recent["close"].iloc[-1])

    support = float(recent["low"].min())
    resistance = float(recent["high"].max())

    distance_support = current - support
    distance_resistance = resistance - current

    score = 50
    signal = "HOLD"
    confidence = 50
    reason = "Price between support and resistance"

    # ==========================================================
    # Close to Support
    # ==========================================================

    if distance_support <= max(current * 0.003, 15):

        signal = "BUY"
        score = 80
        confidence = 80
        reason = "Price near support"

    # ==========================================================
    # Close to Resistance
    # ==========================================================

    elif distance_resistance <= max(current * 0.003, 15):

        signal = "SELL"
        score = 20
        confidence = 80
        reason = "Price near resistance"

    # ==========================================================
    # Mid Zone
    # ==========================================================

    else:

        signal = "HOLD"
        score = 50
        confidence = 55

    support_strength = (
        recent["low"].round(2).value_counts().max()
    )

    resistance_strength = (
        recent["high"].round(2).value_counts().max()
    )

    return {

        "signal": signal,

        "score": score,

        "confidence": confidence,

        "reason": reason,

        "support": round(support, 2),

        "resistance": round(resistance, 2),

        "current_price": round(current, 2),

        "distance_to_support": round(distance_support, 2),

        "distance_to_resistance": round(distance_resistance, 2),

        "support_strength": int(support_strength),

        "resistance_strength": int(resistance_strength)

    }