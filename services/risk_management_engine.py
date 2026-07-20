"""
Risk Management Engine V3
"""

from typing import Dict


def calculate_trade_levels(
    indicators: Dict,
    signal: str,
):

    current = float(indicators["CLOSE"])

    atr = float(indicators["ATR"])

    support = float(
        indicators.get(
            "SUPPORT",
            current - (2 * atr),
        )
    )

    resistance = float(
        indicators.get(
            "RESISTANCE",
            current + (2 * atr),
        )
    )

    # =====================================================
    # BUY Setup
    # =====================================================

    if signal == "BUY":

        entry = current

        stop_loss = min(
            support,
            current - (1.5 * atr),
        )

        target1 = current + (2 * atr)

        target2 = current + (3 * atr)

        target3 = current + (5 * atr)

    # =====================================================
    # SELL Setup
    # =====================================================

    elif signal == "SELL":

        entry = current

        stop_loss = max(
            resistance,
            current + (1.5 * atr),
        )

        target1 = current - (2 * atr)

        target2 = current - (3 * atr)

        target3 = current - (5 * atr)

    # =====================================================
    # HOLD
    # =====================================================

    else:

        return {

            "signal": "HOLD",

            "score": 50,

            "reason": "No trade",

            "ENTRY": round(current, 2),

            "STOP_LOSS": None,

            "TARGET1": None,

            "TARGET2": None,

            "TARGET3": None,

            "RR": 0

        }

    # =====================================================
    # Risk Reward
    # =====================================================

    risk = abs(entry - stop_loss)

    reward = abs(target2 - entry)

    rr = round(reward / risk, 2) if risk else 0

    # =====================================================
    # Score
    # =====================================================

    score = 80

    if rr >= 2.5:

        score = 95

    elif rr >= 2:

        score = 90

    elif rr >= 1.5:

        score = 80

    elif rr >= 1:

        score = 65

    else:

        score = 40

    return {

        "signal": signal,

        "score": score,

        "reason": f"Risk Reward {rr}:1",

        "ENTRY": round(entry, 2),

        "SUPPORT": round(support, 2),

        "RESISTANCE": round(resistance, 2),

        "STOP_LOSS": round(stop_loss, 2),

        "TARGET1": round(target1, 2),

        "TARGET2": round(target2, 2),

        "TARGET3": round(target3, 2),

        "ATR": round(atr, 2),

        "RR": rr

    }