"""
Order Manager

Coordinates the execution of validated trades.

Responsibilities
----------------
✓ Prevent duplicate orders
✓ Track active orders
✓ Enforce maximum open trades
✓ Enforce daily trade limits
✓ Submit approved orders to OrderExecutor

Does NOT
--------
✗ Calculate indicators
✗ Validate market conditions
✗ Calculate risk
✗ Communicate directly with the broker
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from services.execution.order_executor import OrderExecutor

LOGGER = logging.getLogger(__name__)


class OrderManager:

    def __init__(
        self,
        max_open_trades: int = 3,
        max_daily_trades: int = 20,
    ):

        self.executor = OrderExecutor()

        self.max_open_trades = max_open_trades
        self.max_daily_trades = max_daily_trades

        self.active_orders: dict[str, dict[str, Any]] = {}

        self.daily_trade_count = 0

        self.trade_day = date.today()

    # --------------------------------------------------

    def submit_order(
        self,
        order: dict[str, Any],
    ) -> dict[str, Any]:

        self._reset_day()

        symbol = order["symbol"]

        if self.daily_trade_count >= self.max_daily_trades:

            return self._reject(
                "Daily trade limit reached."
            )

        if symbol in self.active_orders:

            return self._reject(
                f"Active order already exists for {symbol}."
            )

        if len(self.active_orders) >= self.max_open_trades:

            return self._reject(
                "Maximum open trades reached."
            )

        result = self.executor.execute(order)

        if result["success"]:

            self.active_orders[symbol] = {

                "order": order,

                "response": result,

            }

            self.daily_trade_count += 1

        return result

    # --------------------------------------------------

    def close_order(
        self,
        symbol: str,
    ):

        self.active_orders.pop(symbol, None)

    # --------------------------------------------------

    def has_active_order(
        self,
        symbol: str,
    ) -> bool:

        return symbol in self.active_orders

    # --------------------------------------------------

    def active_order_count(
        self,
    ) -> int:

        return len(self.active_orders)

    # --------------------------------------------------

    def summary(
        self,
    ) -> dict[str, Any]:

        return {

            "active_orders": len(self.active_orders),

            "daily_trade_count": self.daily_trade_count,

            "max_open_trades": self.max_open_trades,

            "max_daily_trades": self.max_daily_trades,

            "symbols": list(self.active_orders.keys()),

        }

    # --------------------------------------------------

    def _reset_day(
        self,
    ):

        today = date.today()

        if today != self.trade_day:

            self.trade_day = today

            self.daily_trade_count = 0

    # --------------------------------------------------

    @staticmethod
    def _reject(
        message: str,
    ) -> dict[str, Any]:

        LOGGER.warning(message)

        return {

            "success": False,

            "status": "REJECTED",

            "message": message,

        }