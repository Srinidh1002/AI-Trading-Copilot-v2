"""
Learning Engine

Tracks completed trades and stores them permanently
using the Memory Engine.
"""

from typing import Dict, List

from services.memory_engine import memory_engine


class LearningEngine:

    def __init__(self):

        self.trade_history: List[Dict] = (
            memory_engine.get_all_trades()
        )

    def record_trade(
        self,
        trade: Dict,
    ) -> None:

        self.trade_history.append(trade)

        memory_engine.add_trade(trade)

    def total_trades(self) -> int:

        return len(self.trade_history)

    def winning_trades(self) -> int:

        return sum(
            1
            for trade in self.trade_history
            if trade.get("result") == "WIN"
        )

    def losing_trades(self) -> int:

        return sum(
            1
            for trade in self.trade_history
            if trade.get("result") == "LOSS"
        )

    def pending_trades(self) -> int:

        return sum(
            1
            for trade in self.trade_history
            if trade.get("result") == "PENDING"
        )

    def win_rate(self) -> float:

        completed = (
            self.winning_trades()
            + self.losing_trades()
        )

        if completed == 0:
            return 0.0

        return round(
            (self.winning_trades() / completed) * 100,
            2,
        )

    def summary(self) -> Dict:

        return {

            "total_trades": self.total_trades(),

            "winning_trades": self.winning_trades(),

            "losing_trades": self.losing_trades(),

            "pending_trades": self.pending_trades(),

            "win_rate": self.win_rate(),

        }


learning_engine = LearningEngine()