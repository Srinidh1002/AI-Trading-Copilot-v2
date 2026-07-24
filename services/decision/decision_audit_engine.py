"""
Decision Audit Engine

Creates a complete audit trail for every trade decision.

This engine NEVER changes a decision.
It only records how the final decision was reached.
"""

from datetime import datetime


def _build_votes(
    decision,
    confidence,
    risk,
    trade_score,
    trade_filters,
    master_decision,
):
    """
    Record how every engine voted.
    """

    return [
        {
            "engine": "Decision Engine",
            "approved": decision.get("approved", False),
        },
        {
            "engine": "Confidence Engine",
            "approved": confidence.get("confidence", 0) >= 70,
            "confidence": confidence.get("confidence", 0),
        },
        {
            "engine": "Risk Engine",
            "approved": risk.get("approved", False),
        },
        {
            "engine": "Trade Score Engine",
            "approved": trade_score.get("approved", False),
            "score": trade_score.get("trade_score"),
        },
        {
            "engine": "Trade Filter Engine",
            "approved": trade_filters.get("approved", False),
        },
        {
            "engine": "Master Decision Engine",
            "approved": master_decision.get("approved", False),
        },
    ]


def _build_timeline(
    decision,
    confidence,
    risk,
    trade_score,
    trade_filters,
    master_decision,
):
    """
    Build the decision processing timeline.
    """

    return [
        {
            "step": 1,
            "engine": "Decision Engine",
            "approved": decision.get("approved", False),
        },
        {
            "step": 2,
            "engine": "Confidence Engine",
            "approved": confidence.get("confidence", 0) >= 70,
        },
        {
            "step": 3,
            "engine": "Risk Engine",
            "approved": risk.get("approved", False),
        },
        {
            "step": 4,
            "engine": "Trade Score Engine",
            "approved": trade_score.get("approved", False),
        },
        {
            "step": 5,
            "engine": "Trade Filter Engine",
            "approved": trade_filters.get("approved", False),
        },
        {
            "step": 6,
            "engine": "Master Decision Engine",
            "approved": master_decision.get("approved", False),
        },
    ]


def _build_reject_reasons(
    decision,
    confidence,
    risk,
    trade_score,
    trade_filters,
    master_decision,
):
    """
    Collect rejection reasons from every engine.
    """

    reasons = []

    if not decision.get("approved", False):
        reason = decision.get("reason")
        if reason:
            reasons.append(
                {
                    "engine": "Decision Engine",
                    "reason": reason,
                }
            )

    if not risk.get("approved", False):
        reason = risk.get("reason")
        if reason:
            reasons.append(
                {
                    "engine": "Risk Engine",
                    "reason": reason,
                }
            )

    if not trade_score.get("approved", False):
        reason = trade_score.get("reason")
        if reason:
            reasons.append(
                {
                    "engine": "Trade Score Engine",
                    "reason": reason,
                }
            )

    if not trade_filters.get("approved", False):
        for reason in trade_filters.get(
            "reasons",
            [],
        ):
            reasons.append(
                {
                    "engine": "Trade Filter Engine",
                    "reason": reason,
                }
            )

    if not master_decision.get("approved", False):
        reason = master_decision.get("reason")
        if reason:
            reasons.append(
                {
                    "engine": "Master Decision Engine",
                    "reason": reason,
                }
            )

    return reasons


def _build_summary(
    votes,
    reject_reasons,
    master_decision,
):
    """
    Build a high-level summary of the decision.
    """

    approved_votes = sum(
        vote["approved"]
        for vote in votes
    )

    rejected_votes = len(votes) - approved_votes

    return {
        "final_decision": master_decision.get("decision"),
        "approved": master_decision.get("approved", False),
        "approved_votes": approved_votes,
        "rejected_votes": rejected_votes,
        "total_rejections": len(reject_reasons),
    }


def build_decision_audit(
    *,
    snapshot,
    decision,
    confidence,
    risk,
    trade_score,
    trade_filters,
    master_decision,
):
    """
    Build a complete audit record for a trade decision.
    """

    votes = _build_votes(
        decision,
        confidence,
        risk,
        trade_score,
        trade_filters,
        master_decision,
    )

    timeline = _build_timeline(
        decision,
        confidence,
        risk,
        trade_score,
        trade_filters,
        master_decision,
    )

    reject_reasons = _build_reject_reasons(
        decision,
        confidence,
        risk,
        trade_score,
        trade_filters,
        master_decision,
    )

    summary = _build_summary(
        votes,
        reject_reasons,
        master_decision,
    )

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "symbol": snapshot.get("symbol"),
        "decision": decision,
        "confidence": confidence,
        "risk": risk,
        "trade_score": trade_score,
        "trade_filters": trade_filters,
        "master_decision": master_decision,
        "timeline": timeline,
        "votes": votes,
        "reject_reasons": reject_reasons,
        "summary": summary,
    }