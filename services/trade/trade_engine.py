"""
Trade Engine

Main orchestrator of the AI Trading Copilot.
"""

from services.core.market_snapshot import get_market_snapshot
from services.decision.master_decision_engine import make_decision
from services.risk.risk_engine import calculate_risk


def generate_trade():
    """
    Complete AI trade pipeline.

    Returns
    -------
    dict
    """

    snapshot = get_market_snapshot()

    decision = make_decision(snapshot)

    risk = calculate_risk(
        snapshot,
        decision,
    )

    return {
        "snapshot": snapshot,
        "decision": decision,
        "risk": risk,
    }