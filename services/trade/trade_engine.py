"""
Trade Engine

Institutional AI Trade Engine
"""

import math
from collections.abc import Mapping

from services.core.market_snapshot import get_market_snapshot
from services.decision.master_decision_engine import make_decision
from services.risk.risk_engine import calculate_risk
from services.trade.trade_score_engine import TradeScoreEngine
from services.trade.paper_trade_engine import (
    process_trade,
)
from services.refresh import refresh_state
from services.performance import performance_monitor
from services.confidence_engine import (
    calculate_confidence,
)
from services.decision.master_decision_engine import (
    make_master_decision,
)
from services.trade.trade_response_builder import (
    build_trade_response,
)

trade_score_engine = TradeScoreEngine()


def _paper_execution_rejection(reason):
    return {
        "status": "REJECTED",
        "executed": False,
        "reason": reason,
        "paper_trade": None,
    }


def _positive_finite_number(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def execute_paper_trade(analysis_result):
    """Explicitly submit an already-produced analysis result to paper trading.

    Analysis callers, including the dashboard, must call ``analyze_trade``
    only. Paper-trading mutation is intentionally opt-in through this boundary.
    An execution request must carry an approved, directional analysis response.
    """

    if not isinstance(analysis_result, Mapping):
        return _paper_execution_rejection(
            "Analysis result must be a mapping."
        )

    action = str(analysis_result.get("decision", "")).upper()
    direction = {
        "BUY CE": "BUY",
        "BUY": "BUY",
        "BUY PE": "SELL",
        "SELL": "SELL",
    }.get(action)
    if direction is None:
        return _paper_execution_rejection(
            "A directional BUY or SELL decision is required."
        )

    if analysis_result.get("trade_action") != "EXECUTE":
        return _paper_execution_rejection(
            "Execution status is not approved."
        )

    if (
        analysis_result.get("approval_status") != "APPROVED"
        or analysis_result.get("entry_allowed") is not True
        or analysis_result.get("master_decision") != direction
    ):
        return _paper_execution_rejection(
            "Explicit directional authorization is required."
        )

    if analysis_result.get("error"):
        return _paper_execution_rejection(
            "Analysis result contains an internal error."
        )

    risk_level = str(analysis_result.get("risk_level", "")).upper()
    if risk_level in {"HIGH", "REJECTED", "BLOCKED", "ERROR"}:
        return _paper_execution_rejection(
            "Risk validation did not approve paper execution."
        )

    snapshot = analysis_result.get("snapshot")
    if not isinstance(snapshot, Mapping):
        return _paper_execution_rejection(
            "A valid market snapshot is required."
        )

    timestamp = snapshot.get("timestamp")
    if not isinstance(timestamp, str) or not timestamp.strip():
        return _paper_execution_rejection(
            "Snapshot timestamp is required."
        )

    fields = {
        "entry": analysis_result.get("entry"),
        "stop_loss": analysis_result.get("stop_loss"),
        "target1": analysis_result.get("target1"),
        "target2": analysis_result.get("target2"),
        "confidence": analysis_result.get("confidence"),
        "current_price": snapshot.get("ltp"),
    }
    numeric_fields = {
        name: _positive_finite_number(value)
        for name, value in fields.items()
    }
    if any(value is None for value in numeric_fields.values()):
        return _paper_execution_rejection(
            "Trade plan contains missing or invalid numeric values."
        )

    if "quantity" in analysis_result and _positive_finite_number(
        analysis_result["quantity"]
    ) is None:
        return _paper_execution_rejection(
            "Quantity must be a positive finite number."
        )

    reason = analysis_result.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return _paper_execution_rejection(
            "Execution reason is required."
        )

    paper_trade = {
        "timestamp": timestamp,
        "decision": direction,
        "trade_action": "EXECUTE",
        "entry": numeric_fields["entry"],
        "stop_loss": numeric_fields["stop_loss"],
        "target1": numeric_fields["target1"],
        "target2": numeric_fields["target2"],
        "confidence": numeric_fields["confidence"],
        "reason": reason,
        "current_price": numeric_fields["current_price"],
    }

    try:
        process_trade(paper_trade)
    except Exception:
        return _paper_execution_rejection(
            "Paper trade execution failed."
        )

    return {
        "status": "SUBMITTED",
        "executed": True,
        "reason": "Paper trade submitted.",
        "paper_trade": paper_trade,
    }


def generate_trade():

    return analyze_trade()
def _strength_label(confidence: float) -> str:

    if confidence >= 90:
        return "Very Strong"

    if confidence >= 75:
        return "Strong"

    if confidence >= 60:
        return "Moderate"

    return "Weak"
def _targets(
    signal: str,
    entry: float,
    stop_loss: float,
):

    risk_distance = abs(entry - stop_loss)

    if signal == "BUY":

        return (
            round(entry + risk_distance, 2),
            round(entry + (risk_distance * 1.5), 2),
            round(entry + (risk_distance * 2.0), 2),
        )

    elif signal == "SELL":

        return (
            round(entry - risk_distance, 2),
            round(entry - (risk_distance * 1.5), 2),
            round(entry - (risk_distance * 2.0), 2),
        )

    return (
        entry,
        entry,
        entry,
    )
def _momentum_label(
    bull: float,
    bear: float,
) -> str:

    if bull > bear:
        return "Bullish"

    if bear > bull:
        return "Bearish"

    return "Neutral"

def analyze_trade(snapshot=None):
    performance_monitor.start("decision_engine")
    if snapshot is None:

        snapshot = get_market_snapshot()

    if refresh_state.decision is None:

        decision = make_decision(snapshot)

        refresh_state.decision = decision

    else:

        decision = refresh_state.decision

    risk = calculate_risk(
        snapshot,
        decision,
    )

    trade_score = trade_score_engine.evaluate(
        snapshot,
        decision,
    )
    confidence_result = calculate_confidence(
        technical={
            "bull_score": decision.get("bull_score", 0),
            "bear_score": decision.get("bear_score", 0),
            "indicators": snapshot.get("indicators", {}),
        },
        market={
            "trend": decision.get(
                "signal",
                "HOLD",
            ),
            "market_regime": snapshot.get(
                "market_regime",
                "UNKNOWN",
            ),
        },
        option=snapshot.get(
            "option_analysis",
            {},
        ),
        sentiment=snapshot.get(
            "sentiment",
            {},
        ),
        strategy={
            "signal": decision.get(
                "signal",
                "HOLD",
            ),
        },
        smart_money=snapshot.get(
            "smart_money",
            {},
        ),
        risk={
            "risk_reward": risk.get(
                "risk_reward",
            ),
        },
    )
    bull = round(
    decision.get("bull_score", 0),
    2,
    )

    bear = round(
        decision.get("bear_score", 0),
        2,
    )

    signal = decision.get(
        "signal",
        "HOLD",
    )
    master_decision = make_master_decision(
    technical={
        "bull_score": bull,
        "bear_score": bear,
    },
    market={
        "trend": signal,
    },
    option=snapshot.get(
        "option_analysis",
        {},
    ),
    sentiment=snapshot.get(
        "sentiment",
        {},
    ),
    strategy={
        "signal": signal,
    },
    confidence=confidence_result,
    market_regime={
        "regime": snapshot.get(
            "market_regime",
            "UNKNOWN",
        ),
    },
    decision_validator=snapshot.get(
        "decision_validator",
        {},
    ),
    multi_timeframe=snapshot.get(
        "multi_timeframe",
        {},
    ),
    trade_quality={
        "overall_score": trade_score.get(
            "Score",
            0,
        ),
        "grade": trade_score.get(
            "Grade",
            "",
        ),
        "risk_level": trade_score.get(
            "RiskLevel",
            "",
        ),
        "should_trade": signal in {
            "BUY",
            "SELL",
        },
    },
    evidence=snapshot.get(
        "evidence",
        {},
    ),
)
    master_signal = master_decision.get(
    "final_decision",
    "NO_TRADE",
)

    if master_signal == "BUY":

        signal = "BUY"

    elif master_signal == "SELL":

        signal = "SELL"

    else:

        signal = "HOLD"
    
    display_signal = {
        "BUY": "BUY CE",
        "SELL": "BUY PE",
    }.get(signal, "WAIT")

    confidence = round(
        confidence_result.get(
            "confidence",
            decision.get(
                "confidence",
                0,
            ),
        ),
        2,
    )

    trend = {

        "trend": signal,

        "momentum": _momentum_label(
            bull,
            bear,
        ),

        "strength": _strength_label(confidence),

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

    target1, target2, target3 = _targets(
        signal,
        entry,
        stop_loss,
    )

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
        ai_reason.append(f"Trend: {trend['momentum']}")

    if decision.get("option_bias"):
        ai_reason.append(f"Options: {decision['option_bias']}")

    if decision.get("greeks_bias"):
        ai_reason.append(f"Greeks: {decision['greeks_bias']}")

    if decision.get("pcr") is not None:
        ai_reason.append(f"PCR: {decision['pcr']}")

    if decision.get("option_flow"):
        ai_reason.append(f"Flow: {decision['option_flow']}")

    ai_reason.extend(trade_score["Reasons"])

    if signal == "BUY":
        ai_reason.append("BUY conditions satisfied")
    elif signal == "SELL":
        ai_reason.append("SELL conditions satisfied")
    else:
        ai_reason.append("Awaiting confirmation")


    reason = confidence_result.get(
        "reason",
        " | ".join(
            dict.fromkeys(ai_reason)
        ),
    )

    performance_monitor.stop("decision_engine")
    return build_trade_response(
        display_signal=display_signal,
        master_decision=master_decision,
        confidence=confidence,
        reason=reason,
        entry=entry,
        stop_loss=stop_loss,
        target1=target1,
        target2=target2,
        target3=target3,
        bull=bull,
        bear=bear,
        trend=trend,
        pattern=pattern,
        support_resistance=support_resistance,
        trade_score=trade_score,
        confidence_result=confidence_result,
        risk_dashboard=risk_dashboard,
        snapshot=snapshot,
        decision=decision,
        risk=risk,
    )
