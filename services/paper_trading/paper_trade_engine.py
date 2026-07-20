"""
Paper Trading Engine

Simulates trades without sending real orders.
"""

from datetime import datetime

paper_positions = []


def execute_paper_trade(
    decision,
    risk,
):
    """
    Execute a simulated trade.

    Returns
    -------
    dict
    """

    if decision["signal"] == "HOLD":

        return {
            "status": "NO_TRADE",
            "reason": "Decision engine returned HOLD.",
        }

    trade = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "signal": decision["signal"],
        "entry": risk["entry"],
        "stop_loss": risk["stop_loss"],
        "target": risk["target"],
        "status": "OPEN",
    }

    paper_positions.append(trade)

    return {
        "status": "SUCCESS",
        "trade": trade,
        "open_positions": len(paper_positions),
    }


def get_open_positions():
    """
    Return all open paper trades.
    """

    return paper_positions