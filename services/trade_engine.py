"""
Trade Engine V0.5
"""

from services.trend_engine import analyze_trend


def analyze_trade(snapshot):

    trend_data = analyze_trend(snapshot)

    trend = trend_data["trend"]
    strength = trend_data["strength"]
    momentum = trend_data["momentum"]

    if trend == "Bullish" and momentum == "Bullish":
        decision = "BUY"

    elif trend == "Bearish" and momentum == "Bearish":
        decision = "SELL"

    else:
        decision = "WAIT"

    return {
        "decision": decision,
        "trend": trend,
        "strength": strength,
        "momentum": momentum,
    }


# =====================================================
# Backward Compatibility
# =====================================================

def trade_recommendation(*args, **kwargs):
    """
    Temporary compatibility function for the old dashboard.
    We'll replace it completely later.
    """
    return {
        "signal": "WAIT",
        "confidence": 0,
        "reason": "Legacy trade engine placeholder"
    }