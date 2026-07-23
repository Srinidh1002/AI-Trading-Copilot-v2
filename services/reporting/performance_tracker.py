"""
Performance Tracker

Tracks completed trades and calculates
strategy performance statistics.
"""

from datetime import datetime


class PerformanceTracker:

    def __init__(self):

        self.trades = []

    def add_trade(

        self,

        symbol,

        signal,

        entry,

        exit_price,

        quantity,

    ):

        pnl = (exit_price - entry) * quantity

        if signal.upper() == "SELL":

            pnl *= -1

        trade = {

            "timestamp": datetime.now(),

            "symbol": symbol,

            "signal": signal,

            "entry": entry,

            "exit": exit_price,

            "quantity": quantity,

            "pnl": round(
                pnl,
                2,
            ),

            "win": pnl > 0,

        }

        self.trades.append(trade)

        return trade

    def summary(self):

        if not self.trades:

            return {

                "total_trades": 0,

                "wins": 0,

                "losses": 0,

                "win_rate": 0,

                "total_pnl": 0,

                "average_pnl": 0,

                "largest_profit": 0,

                "largest_loss": 0,

            }

        total = len(self.trades)

        wins = sum(

            t["win"]

            for t in self.trades

        )

        losses = total - wins

        pnl = [

            t["pnl"]

            for t in self.trades

        ]

        return {

            "total_trades": total,

            "wins": wins,

            "losses": losses,

            "win_rate": round(

                wins * 100 / total,

                2,

            ),

            "total_pnl": round(

                sum(pnl),

                2,

            ),

            "average_pnl": round(

                sum(pnl) / total,

                2,

            ),

            "largest_profit": round(

                max(pnl),

                2,

            ),

            "largest_loss": round(

                min(pnl),

                2,

            ),

        }

    def history(self):

        return self.trades