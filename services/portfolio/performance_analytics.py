"""
Performance Analytics

Provides institutional-grade performance metrics
for strategy evaluation and portfolio analysis.

Responsibilities
----------------
✓ Equity curve
✓ ROI
✓ Profit Factor
✓ Expectancy
✓ Average R Multiple
✓ Max Drawdown
✓ Consecutive Wins/Losses
✓ Performance Summary
"""

from __future__ import annotations

from typing import Any


class PerformanceAnalytics:

    def __init__(self):

        self.trades: list[dict[str, Any]] = []

    # --------------------------------------------------

    def add_trade(
        self,
        trade: dict[str, Any],
    ):

        self.trades.append(trade)

    # --------------------------------------------------

    def total_trades(self) -> int:

        return len(self.trades)

    # --------------------------------------------------

    def net_profit(self) -> float:

        return round(

            sum(
                trade.get(
                    "realized_pnl",
                    0.0,
                )
                for trade in self.trades
            ),

            2,

        )

    # --------------------------------------------------

    def gross_profit(self) -> float:

        return round(

            sum(

                trade["realized_pnl"]

                for trade in self.trades

                if trade["realized_pnl"] > 0

            ),

            2,

        )

    # --------------------------------------------------

    def gross_loss(self) -> float:

        return round(

            abs(

                sum(

                    trade["realized_pnl"]

                    for trade in self.trades

                    if trade["realized_pnl"] < 0

                )

            ),

            2,

        )

    # --------------------------------------------------

    def profit_factor(self) -> float:

        loss = self.gross_loss()

        if loss == 0:
            return 0.0

        return round(

            self.gross_profit() / loss,

            2,

        )

    # --------------------------------------------------

    def roi(
        self,
        initial_capital: float,
    ) -> float:

        if initial_capital <= 0:
            return 0.0

        return round(

            (self.net_profit() / initial_capital)

            * 100,

            2,

        )

    # --------------------------------------------------

    def expectancy(self) -> float:

        if not self.trades:
            return 0.0

        return round(

            self.net_profit()

            / len(self.trades),

            2,

        )

    # --------------------------------------------------

    def max_drawdown(self) -> float:

        equity = 0.0

        peak = 0.0

        drawdown = 0.0

        for trade in self.trades:

            equity += trade.get(
                "realized_pnl",
                0.0,
            )

            peak = max(
                peak,
                equity,
            )

            drawdown = max(
                drawdown,
                peak - equity,
            )

        return round(drawdown, 2)

    # --------------------------------------------------

    def consecutive_results(self):

        wins = 0

        losses = 0

        max_wins = 0

        max_losses = 0

        for trade in self.trades:

            pnl = trade.get(
                "realized_pnl",
                0.0,
            )

            if pnl > 0:

                wins += 1

                losses = 0

            elif pnl < 0:

                losses += 1

                wins = 0

            max_wins = max(
                max_wins,
                wins,
            )

            max_losses = max(
                max_losses,
                losses,
            )

        return {

            "max_consecutive_wins": max_wins,

            "max_consecutive_losses": max_losses,

        }

    # --------------------------------------------------

    def equity_curve(self):

        curve = []

        equity = 0.0

        for trade in self.trades:

            equity += trade.get(
                "realized_pnl",
                0.0,
            )

            curve.append(round(equity, 2))

        return curve

    # --------------------------------------------------

    def summary(
        self,
        initial_capital: float,
    ):

        summary = {

            "total_trades": self.total_trades(),

            "net_profit": self.net_profit(),

            "gross_profit": self.gross_profit(),

            "gross_loss": self.gross_loss(),

            "profit_factor": self.profit_factor(),

            "roi_percent": self.roi(
                initial_capital,
            ),

            "expectancy": self.expectancy(),

            "max_drawdown": self.max_drawdown(),

            "equity_curve": self.equity_curve(),

        }

        summary.update(
            self.consecutive_results()
        )

        return summary

    # --------------------------------------------------

    def reset(self):

        self.trades.clear()