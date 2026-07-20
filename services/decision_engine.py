"""
Decision Engine V2
Weighted Voting Engine
"""

from typing import Dict


def make_decision(
    trend_result: Dict,
    candle_result: Dict,
    support_result: Dict,
    risk_result: Dict = None,
    option_result: Dict = None,
    news_result: Dict = None,
    volume_result: Dict = None,
):

    buy_votes = 0
    sell_votes = 0
    hold_votes = 0

    buy_strength = 0
    sell_strength = 0
    hold_strength = 0

    reasons = []

    engines = [

        ("Trend", trend_result),

        ("Candlestick", candle_result),

        ("Support", support_result),

        ("Risk", risk_result),

        ("Option", option_result),

        ("News", news_result),

        ("Volume", volume_result),

    ]

    for name, result in engines:

        if result is None:
            continue

        signal = str(
            result.get(
                "signal",
                "HOLD"
            )
        ).upper()

        score = float(
            result.get(
                "score",
                50
            )
        )

        reason = result.get("reason", "")

        if reason:
            reasons.append(
                f"{name}: {reason}"
            )

        if signal == "BUY":

            buy_votes += 1

            buy_strength += score

        elif signal == "SELL":

            sell_votes += 1

            sell_strength += 100 - score

        else:

            hold_votes += 1

            hold_strength += 50

    total_strength = (

        buy_strength +

        sell_strength +

        hold_strength

    )

    if total_strength == 0:

        return {

            "signal": "HOLD",

            "buy_votes": 0,

            "sell_votes": 0,

            "hold_votes": 0,

            "buy_strength": 0,

            "sell_strength": 0,

            "hold_strength": 0,

            "confidence": 0,

            "reason": "No engine output."

        }

    if (

        buy_strength >

        sell_strength

        and

        buy_strength >

        hold_strength

    ):

        signal = "BUY"

        confidence = round(
            (buy_strength / total_strength) * 100,
            2
        )

    elif (

        sell_strength >

        buy_strength

        and

        sell_strength >

        hold_strength

    ):

        signal = "SELL"

        confidence = round(
            (sell_strength / total_strength) * 100,
            2
        )

    else:

        signal = "HOLD"

        confidence = round(
            (hold_strength / total_strength) * 100,
            2
        )

    return {

        "signal": signal,

        "confidence": confidence,

        "buy_votes": buy_votes,

        "sell_votes": sell_votes,

        "hold_votes": hold_votes,

        "buy_strength": round(buy_strength, 2),

        "sell_strength": round(sell_strength, 2),

        "hold_strength": round(hold_strength, 2),

        "reason": " | ".join(reasons),

    }