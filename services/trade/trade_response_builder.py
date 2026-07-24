"""
Trade Response Builder

Builds the final response contract returned by the Trade Engine.
This module performs no calculations or decisions.
"""
from services.trade.trade_context import TradeContext

def build_trade_response(
    context: TradeContext,
):

    return {

        # ==========================
        # FINAL DECISION
        # ==========================

        "decision": context.display_signal,

        "master_decision": context.master_decision.get(
            "final_decision",
        ),

        "approval_status": context.master_decision.get(
            "approval_status",
        ),

        "entry_allowed": context.master_decision.get(
            "entry_allowed",
        ),

        "decision_score": context.master_decision.get(
            "decision_score",
        ),

        "decision_summary": context.master_decision.get(
            "summary",
        ),

        "confidence": context.confidence,

        "reason": context.reason,

        # ==========================
        # TRADE PLAN
        # ==========================

        "entry": context.entry,

        "stop_loss": context.stop_loss,

        "target1": context.target1,

        "target2": context.target2,

        "target3": context.target3,

        # ==========================
        # SCORES
        # ==========================

        "bull_score": context.bull,

        "bear_score": context.bear,

        "neutral_score": max(
            0,
            round(
                10 - context.bull - context.bear,
                2,
            ),
        ),

        # ==========================
        # DASHBOARD
        # ==========================

        "trend": context.trend,

        "pattern": context.pattern,

        "support_resistance": context.support_resistance,

        "institutional_score": context.trade_score["Score"],

        "trade_grade": context.confidence_result.get(
            "grade",
            context.trade_score["Grade"],
        ),

        "trade_quality": context.confidence_result.get(
            "trade_quality",
            "UNKNOWN",
        ),

        "trade_action": context.trade_score["Action"],

        "risk_level": context.trade_score["RiskLevel"],

        "risk": context.risk_dashboard,

        # ==========================
        # RAW DATA
        # ==========================

        "snapshot": context.snapshot,

        "decision_data": context.decision,

        "master_decision_data": context.master_decision,

        "risk_data": context.risk,

        "trade_score_data": context.trade_score,
    }