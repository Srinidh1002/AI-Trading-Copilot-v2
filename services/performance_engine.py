"""
Performance Engine

Analyzes the historical performance of the AI Trading Copilot
and generates performance metrics used for future learning.
"""

from typing import Dict

from services.learning_engine import learning_engine


class PerformanceEngine:

    def __init__(self):
        pass

    def report(self) -> Dict:

        summary = learning_engine.summary()

        total = summary["total_trades"]
        wins = summary["winning_trades"]
        losses = summary["losing_trades"]
        pending = summary["pending_trades"]
        win_rate = summary["win_rate"]

        performance = "NO_DATA"

        if total > 0:

            if win_rate >= 70:
                performance = "EXCELLENT"

            elif win_rate >= 60:
                performance = "GOOD"

            elif win_rate >= 50:
                performance = "AVERAGE"

            else:
                performance = "POOR"

        return {

            "performance": performance,

            "total_trades": total,

            "winning_trades": wins,

            "losing_trades": losses,

            "pending_trades": pending,

            "win_rate": win_rate,

        }


performance_engine = PerformanceEngine()