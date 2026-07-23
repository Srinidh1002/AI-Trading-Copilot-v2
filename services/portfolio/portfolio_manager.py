"""
Portfolio Manager

Maintains portfolio state for both
Paper Trading and Live Trading.

Responsibilities
----------------
✓ Track open positions
✓ Update positions
✓ Close positions
✓ Track realized P&L
✓ Track unrealized P&L
✓ Portfolio summary
"""

from __future__ import annotations

from typing import Any


class PortfolioManager:

    def __init__(self):

        self.positions: dict[str, dict[str, Any]] = {}

        self.realized_pnl = 0.0

    # --------------------------------------------------

    def open_position(
        self,
        symbol: str,
        side: str,
        quantity: int,
        entry_price: float,
    ):

        self.positions[symbol] = {

            "symbol": symbol,

            "side": side.upper(),

            "quantity": int(quantity),

            "entry_price": float(entry_price),

            "last_price": float(entry_price),

            "unrealized_pnl": 0.0,

        }

    # --------------------------------------------------

    def update_price(
        self,
        symbol: str,
        current_price: float,
    ):

        if symbol not in self.positions:
            return

        position = self.positions[symbol]

        position["last_price"] = float(current_price)

        qty = position["quantity"]

        entry = position["entry_price"]

        if position["side"] == "BUY":

            pnl = (current_price - entry) * qty

        else:

            pnl = (entry - current_price) * qty

        position["unrealized_pnl"] = round(
            pnl,
            2,
        )

    # --------------------------------------------------

    def close_position(
        self,
        symbol: str,
        exit_price: float,
    ):

        if symbol not in self.positions:
            return None

        position = self.positions.pop(symbol)

        qty = position["quantity"]

        entry = position["entry_price"]

        if position["side"] == "BUY":

            pnl = (exit_price - entry) * qty

        else:

            pnl = (entry - exit_price) * qty

        pnl = round(pnl, 2)

        self.realized_pnl += pnl

        return {

            "symbol": symbol,

            "side": position["side"],

            "quantity": qty,

            "entry_price": entry,

            "exit_price": float(exit_price),

            "realized_pnl": pnl,

        }

    # --------------------------------------------------

    def get_position(
        self,
        symbol: str,
    ):

        return self.positions.get(symbol)

    # --------------------------------------------------

    def has_position(
        self,
        symbol: str,
    ) -> bool:

        return symbol in self.positions

    # --------------------------------------------------

    def total_unrealized_pnl(
        self,
    ) -> float:

        return round(

            sum(

                p["unrealized_pnl"]

                for p in self.positions.values()

            ),

            2,

        )

    # --------------------------------------------------

    def total_realized_pnl(
        self,
    ) -> float:

        return round(
            self.realized_pnl,
            2,
        )

    # --------------------------------------------------

    def summary(
        self,
    ):

        return {

            "open_positions": len(
                self.positions
            ),

            "realized_pnl": round(
                self.realized_pnl,
                2,
            ),

            "unrealized_pnl": self.total_unrealized_pnl(),

            "positions": self.positions,

        }

    # --------------------------------------------------

    def reset(
        self,
    ):

        self.positions.clear()

        self.realized_pnl = 0.0