"""
Trade Journal

Institutional-grade trade journal for
paper trading and live trading.

Responsibilities
----------------
✓ Record every trade
✓ Maintain complete history
✓ Search trades
✓ Daily statistics
✓ Export-ready records
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


class TradeJournal:

    def __init__(self):

        self.trades: list[dict[str, Any]] = []

    # --------------------------------------------------

    def record_trade(
        self,
        trade: dict[str, Any],
    ):

        entry = {

            "timestamp": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

            **trade,

        }

        self.trades.append(entry)

        return entry

    # --------------------------------------------------

    def all_trades(
        self,
    ):

        return self.trades

    # --------------------------------------------------

    def total_trades(
        self,
    ) -> int:

        return len(self.trades)

    # --------------------------------------------------

    def winning_trades(
        self,
    ):

        return [

            trade

            for trade in self.trades

            if trade.get(
                "realized_pnl",
                0,
            ) > 0

        ]

    # --------------------------------------------------

    def losing_trades(
        self,
    ):

        return [

            trade

            for trade in self.trades

            if trade.get(
                "realized_pnl",
                0,
            ) < 0

        ]

    # --------------------------------------------------

    def trades_by_symbol(
        self,
        symbol: str,
    ):

        return [

            trade

            for trade in self.trades

            if trade.get("symbol") == symbol

        ]

    # --------------------------------------------------

    def trades_by_date(
        self,
        date: str,
    ):

        return [

            trade

            for trade in self.trades

            if trade["timestamp"].startswith(
                date
            )

        ]

    # --------------------------------------------------

    def net_profit(
        self,
    ):

        return round(

            sum(

                trade.get(
                    "realized_pnl",
                    0,
                )

                for trade in self.trades

            ),

            2,

        )

    # --------------------------------------------------

    def summary(
        self,
    ):

        wins = len(
            self.winning_trades()
        )

        losses = len(
            self.losing_trades()
        )

        total = len(
            self.trades
        )

        return {

            "total_trades": total,

            "winning_trades": wins,

            "losing_trades": losses,

            "win_rate": round(

                (wins / total * 100)

                if total

                else 0,

                2,

            ),

            "net_profit": self.net_profit(),

        }

    # --------------------------------------------------

    def clear(
        self,
    ):

        self.trades.clear()