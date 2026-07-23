"""
Trade Engine

Institutional AI Trade Engine
"""

from services.core.market_snapshot import get_market_snapshot
from services.decision.master_decision_engine import make_decision
from services.risk.risk_engine import calculate_risk
from services.trade.trade_score_engine import TradeScoreEngine


trade_score_engine = TradeScoreEngine()


def generate_trade():

    snapshot = get_market_snapshot()

    return analyze_trade(snapshot)


def analyze_trade(snapshot=None):

    if snapshot is None:

        snapshot = get_market_snapshot()

    decision = make_decision(snapshot)

    risk = calculate_risk(
        snapshot,
        decision,
    )

    trade_score = trade_score_engine.evaluate(
        snapshot,
        decision,
    )

    signal = decision.get(
        "signal",
        "HOLD",
    )

    bull = round(
        decision.get(
            "bull_score",
            0,
        ),
        2,
    )

    bear = round(
        decision.get(
            "bear_score",
            0,
        ),
        2,
    )

    confidence = round(
        decision.get(
            "confidence",
            0,
        ),
        2,
    )

    trend = {

        "trend": signal,

        "momentum": (

            "Bullish"

            if bull > bear

            else "Bearish"

            if bear > bull

            else "Neutral"

        ),

        "strength": (

            "Very Strong"

            if confidence >= 90

            else "Strong"

            if confidence >= 75

            else "Moderate"

            if confidence >= 60

            else "Weak"

        ),

        "score": confidence,

    }

    support = decision.get(
        "support",
        snapshot.get("low"),
    )

    resistance = decision.get(
        "resistance",
        snapshot.get("high"),
    )

    support_resistance = {

        "Support": support,

        "Resistance": resistance,

        "OptionSupport": decision.get(
            "option_support",
        ),

        "OptionResistance": decision.get(
            "option_resistance",
        ),

    }

    entry = risk["entry"]

    stop_loss = risk["stop_loss"]

    target = risk["target"]

    if signal == "BUY":

        target1 = round(
            entry + (target - entry) * 0.33,
            2,
        )

        target2 = round(
            entry + (target - entry) * 0.66,
            2,
        )

        target3 = round(
            target,
            2,
        )

    elif signal == "SELL":

        target1 = round(
            entry - (entry - target) * 0.33,
            2,
        )

        target2 = round(
            entry - (entry - target) * 0.66,
            2,
        )

        target3 = round(
            target,
            2,
        )

    else:

        target1 = entry
        target2 = entry
        target3 = entry

    risk_dashboard = {

        "ENTRY": entry,

        "STOPLOSS": stop_loss,

        "TARGET1": target1,

        "TARGET2": target2,

        "TARGET3": target3,

        "RR": risk["risk_reward"],

    }

    pattern = {

        "pattern": snapshot.get(
            "candlestick_pattern",
            "None",
        ),

        "signal": signal,

    }

    ai_reason = []

    if trend["momentum"] != "Neutral":

        ai_reason.append(
            f"Trend {trend['momentum']}"
        )

    if decision.get("option_flow"):

        ai_reason.append(
            decision["option_flow"]
        )

    if decision.get("option_bias"):

        ai_reason.append(
            decision["option_bias"]
        )

    if decision.get("greeks_bias"):

        ai_reason.append(
            f"Greeks {decision['greeks_bias']}"
        )

    if decision.get("pcr") is not None:

        ai_reason.append(
            f"PCR {decision['pcr']}"
        )

    if decision.get("max_pain"):

        ai_reason.append(
            f"Max Pain {decision['max_pain']}"
        )

    ai_reason.extend(
        trade_score["Reasons"]
    )

    if signal == "BUY":

        ai_reason.append(
            "BUY Conditions Met"
        )

    elif signal == "SELL":

        ai_reason.append(
            "SELL Conditions Met"
        )

    else:

        ai_reason.append(
            "Waiting for Confirmation"
        )

    return {

        "snapshot": snapshot,

        "decision": signal,

        "confidence": confidence,

        "bull_score": bull,

        "bear_score": bear,

        "neutral_score": max(
            0,
            round(
                10 - bull - bear,
                2,
            ),
        ),

        "trend": trend,

        "pattern": pattern,

        "support_resistance": support_resistance,

        "entry": entry,

        "stop_loss": stop_loss,

        "target1": target1,

        "target2": target2,

        "risk": risk_dashboard,

        "institutional_score": trade_score["Score"],

        "trade_grade": trade_score["Grade"],

        "trade_action": trade_score["Action"],

        "risk_level": trade_score["RiskLevel"],

        "reason": " | ".join(
            dict.fromkeys(
                ai_reason
            )
        ),

        "decision_data": decision,

        "risk_data": risk,

        "trade_score_data": trade_score,

    }