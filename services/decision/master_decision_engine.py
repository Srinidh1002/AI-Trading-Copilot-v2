"""
Master Decision Engine

Final decision maker.

Combines all analysis engines into a single BUY / SELL / HOLD decision.
"""

from services.analysis.trend_engine import analyze_trend
from services.analysis.market_structure_engine import analyze_market_structure
from services.analysis.candlestick_engine import analyze_candlestick
from services.analysis.support_resistance_engine import (
    analyze_support_resistance,
)
from services.analysis.smart_money_engine import analyze_smart_money


def make_decision(snapshot):
    """
    Generate the final trading decision.

    Returns
    -------
    dict
    """

    trend = analyze_trend(snapshot)
    structure = analyze_market_structure(snapshot)
    candle = analyze_candlestick(snapshot)
    levels = analyze_support_resistance(snapshot)
    smart_money = analyze_smart_money(snapshot)

    bull = 0
    bear = 0
    reasons = []

    if trend["signal"] == "BULLISH":
        bull += trend["bull_score"]
    elif trend["signal"] == "BEARISH":
        bear += trend["bear_score"]

    if structure["signal"] == "UPTREND":
        bull += 2
        reasons.append("Uptrend")

    elif structure["signal"] == "DOWNTREND":
        bear += 2
        reasons.append("Downtrend")

    if candle["signal"] in ["BULLISH", "HAMMER"]:
        bull += 1
        reasons.append(candle["signal"])

    elif candle["signal"] in ["BEARISH", "SHOOTING_STAR"]:
        bear += 1
        reasons.append(candle["signal"])

    if smart_money["signal"] == "STRONG":
        bull += 2
        reasons.append("Strong Smart Money")

    confidence = round(
        max(trend["confidence"], smart_money["confidence"]),
        2,
    )

    if bull > bear:
        signal = "BUY"

    elif bear > bull:
        signal = "SELL"

    else:
        signal = "HOLD"

    return {
        "signal": signal,
        "bull_score": bull,
        "bear_score": bear,
        "confidence": confidence,
        "reason": ", ".join(reasons),
        "support": levels["support"],
        "resistance": levels["resistance"],
    }