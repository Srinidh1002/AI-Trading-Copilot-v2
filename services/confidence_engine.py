"""
Confidence Engine V4
"""

from typing import Dict


def calculate_confidence(decision_result: Dict | None = None, **legacy_signals) -> Dict:
    """Calculate confidence from the current decision payload.

    The keyword-only compatibility path preserves the former diagnostic API.
    """
    if decision_result is None:
        trend = str(legacy_signals.get("trend", "")).lower()
        momentum = str(legacy_signals.get("momentum", "")).lower()
        bullish = trend == "bullish" or momentum == "bullish"
        bearish = trend == "bearish" or momentum == "bearish"

        decision_result = {
            "buy_votes": int(bullish),
            "sell_votes": int(bearish),
            "hold_votes": int(not bullish and not bearish),
            "buy_strength": 1 if bullish else 0,
            "sell_strength": 1 if bearish else 0,
            "hold_strength": 1 if not bullish and not bearish else 0,
            "confidence": 0,
            "reason": "Legacy signal compatibility",
        }

    buy = decision_result.get("buy_votes", 0)
    sell = decision_result.get("sell_votes", 0)
    hold = decision_result.get("hold_votes", 0)

    buy_strength = decision_result.get("buy_strength", 0)
    sell_strength = decision_result.get("sell_strength", 0)
    hold_strength = decision_result.get("hold_strength", 0)

    total_votes = buy + sell + hold

    total_strength = (
        buy_strength
        + sell_strength
        + hold_strength
    )

    if total_votes == 0 or total_strength == 0:

        return {

            "confidence": 0,

            "bull_score": 0,

            "bear_score": 0,

            "neutral_score": 100,

            "reason": "No signals"

        }

    confidence = round(

        decision_result.get("confidence", 0),

        2,

    )

    bull_score = round(

        (buy_strength / total_strength) * 100,

        2,

    )

    bear_score = round(

        (sell_strength / total_strength) * 100,

        2,

    )

    neutral_score = round(

        (hold_strength / total_strength) * 100,

        2,

    )

    return {

        "confidence": confidence,

        "bull_score": bull_score,

        "bear_score": bear_score,

        "neutral_score": neutral_score,

        "reason": decision_result.get("reason", ""),

    }
