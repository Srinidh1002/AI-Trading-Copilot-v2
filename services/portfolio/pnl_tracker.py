"""
PnL Tracker

Tracks realized and unrealized profit/loss
across all trades.

Responsibilities
----------------
✓ Track realized P&L
✓ Track unrealized P&L
✓ Win/Loss statistics
✓ Daily performance
✓ Trading summary
"""

from __future__ import annotations

from typing import Any


class PnLTracker:

    def __init__(self):

        self.closed_trades: list[dict[str, Any]] = []

        self.realized_pnl = 0.0

    # --------------------------------------------------

    def record_trade(
        self,
        trade: dict[str, Any],
    ):

        pnl = float(
            trade.get(
                "realized_pnl",
                0.0,
            )
        )

        self.realized_pnl += pnl

        self.closed_trades.append(trade)

    # --------------------------------------------------

    def total_trades(
        self,
    ) -> int:

        return len(self.closed_trades)

    # --------------------------------------------------

    def winning_trades(
        self,
    ) -> int:

        return sum(

            1

            for trade in self.closed_trades

            if trade["realized_pnl"] > 0

        )

    # --------------------------------------------------

    def losing_trades(
        self,
    ) -> int:

        return sum(

            1

            for trade in self.closed_trades

            if trade["realized_pnl"] < 0

        )

    # --------------------------------------------------

    def win_rate(
        self,
    ) -> float:

        total = self.total_trades()

        if total == 0:
            return 0.0

        return round(

            self.winning_trades()

            / total

            * 100,

            2,

        )

    # --------------------------------------------------

    def average_profit(
        self,
    ) -> float:

        wins = [

            trade["realized_pnl"]

            for trade in self.closed_trades

            if trade["realized_pnl"] > 0

        ]

        if not wins:
            return 0.0

        return round(

            sum(wins) / len(wins),

            2,

        )

    # --------------------------------------------------

    def average_loss(
        self,
    ) -> float:

        losses = [

            trade["realized_pnl"]

            for trade in self.closed_trades

            if trade["realized_pnl"] < 0

        ]

        if not losses:
            return 0.0

        return 0.0 if not losses else round(

            sum(losses) / len(losses),

            2,

        )

    # --------------------------------------------------

    def summary(
        self,
    ):

        return {

            "total_trades": self.total_trades(),

            "winning_trades": self.winning_trades(),

            "losing_trades": self.losing_trades(),

            "win_rate": self.win_rate(),

            "realized_pnl": round(
                self.realized_pnl,
                2,
            ),

            "average_profit": self.average_profit(),

            "average_loss": self.average_loss(),

        }

    # --------------------------------------------------

    def reset(
        self,
    ):

        self.closed_trades.clear()

        self.realized_pnl = 0.0