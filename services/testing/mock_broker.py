"""
Mock Broker

Simulates a broker for paper trading and end-to-end
testing without connecting to a live broker.

Responsibilities
----------------
✓ Login Simulation
✓ Account Information
✓ Order Placement
✓ Order Modification
✓ Order Cancellation
✓ Order Execution
✓ Positions
✓ Holdings
✓ Funds
✓ Trade History
"""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any


class MockBroker:

    def __init__(self):

        self.logged_in = False

        self.account = {
            "client_id": "MOCK001",
            "broker": "Mock Broker",
            "name": "Paper Trading Account",
        }

        self.funds = {
            "opening_balance": 1_000_000.00,
            "available_balance": 1_000_000.00,
            "used_margin": 0.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
        }

        self.orders: list[dict[str, Any]] = []
        self.positions: list[dict[str, Any]] = []
        self.holdings: list[dict[str, Any]] = []
        self.trade_history: list[dict[str, Any]] = []

    # --------------------------------------------------

    def login(
        self,
        user_id: str = "",
        password: str = "",
    ) -> bool:

        self.logged_in = True

        return True

    # --------------------------------------------------

    def logout(self):

        self.logged_in = False

    # --------------------------------------------------

    def is_logged_in(self) -> bool:

        return self.logged_in

    # --------------------------------------------------

    def account_info(self):

        return deepcopy(self.account)

    # --------------------------------------------------

    def funds_info(self):

        return deepcopy(self.funds)

    # --------------------------------------------------

    def place_order(

        self,

        symbol: str,

        side: str,

        quantity: int,

        price: float,

        order_type: str = "MARKET",

    ):

        order = {

            "order_id": str(uuid.uuid4()),

            "timestamp": datetime.now().isoformat(),

            "symbol": symbol,

            "side": side.upper(),

            "quantity": quantity,

            "price": price,

            "order_type": order_type,

            "status": "OPEN",

        }

        self.orders.append(order)

        return deepcopy(order)

    # --------------------------------------------------

    def modify_order(

        self,

        order_id: str,

        quantity: int | None = None,

        price: float | None = None,

    ):

        for order in self.orders:

            if order["order_id"] == order_id:

                if order["status"] != "OPEN":

                    return False

                if quantity is not None:

                    order["quantity"] = quantity

                if price is not None:

                    order["price"] = price

                return True

        return False

    # --------------------------------------------------

    def cancel_order(

        self,

        order_id: str,

    ):

        for order in self.orders:

            if order["order_id"] == order_id:

                if order["status"] != "OPEN":

                    return False

                order["status"] = "CANCELLED"

                return True

        return False

    # --------------------------------------------------

    def execute_order(

        self,

        order_id: str,

        execution_price: float | None = None,

    ):

        for order in self.orders:

            if order["order_id"] != order_id:

                continue

            if order["status"] != "OPEN":

                return False

            fill_price = (

                execution_price

                if execution_price is not None

                else order["price"]

            )

            order["status"] = "EXECUTED"

            order["execution_price"] = fill_price

            order["execution_time"] = datetime.now().isoformat()

            margin = fill_price * order["quantity"]

            self.funds["used_margin"] += margin

            position = {

                "symbol": order["symbol"],

                "side": order["side"],

                "quantity": order["quantity"],

                "average_price": fill_price,

                "ltp": fill_price,

                "unrealized_pnl": 0.0,

            }

            self.positions.append(position)

            self.trade_history.append(deepcopy(order))

            return True

        return False

    # --------------------------------------------------

    def update_market_price(

        self,

        symbol: str,

        ltp: float,

    ):

        total_unrealized = 0.0

        for position in self.positions:

            if position["symbol"] != symbol:

                continue

            position["ltp"] = ltp

            pnl = (

                (ltp - position["average_price"])

                * position["quantity"]

            )

            if position["side"] == "SELL":

                pnl *= -1

            position["unrealized_pnl"] = round(pnl, 2)

            total_unrealized += pnl

        self.funds["unrealized_pnl"] = round(

            total_unrealized,

            2,

        )

    # --------------------------------------------------

    def close_position(

        self,

        symbol: str,

        exit_price: float,

    ):

        remaining = []

        for position in self.positions:

            if position["symbol"] != symbol:

                remaining.append(position)

                continue

            pnl = (

                (exit_price - position["average_price"])

                * position["quantity"]

            )

            if position["side"] == "SELL":

                pnl *= -1

            self.funds["realized_pnl"] += pnl

            self.funds["used_margin"] -= (

                position["average_price"]

                * position["quantity"]

            )

        self.positions = remaining

    # --------------------------------------------------

    def add_holding(

        self,

        symbol: str,

        quantity: int,

        average_price: float,

    ):

        self.holdings.append({

            "symbol": symbol,

            "quantity": quantity,

            "average_price": average_price,

        })

    # --------------------------------------------------

    def orders_list(self):

        return deepcopy(self.orders)

    # --------------------------------------------------

    def positions_list(self):

        return deepcopy(self.positions)

    # --------------------------------------------------

    def holdings_list(self):

        return deepcopy(self.holdings)

    # --------------------------------------------------

    def trades(self):

        return deepcopy(self.trade_history)

    # --------------------------------------------------

    def order(self, order_id: str):

        for order in self.orders:

            if order["order_id"] == order_id:

                return deepcopy(order)

        return None

    # --------------------------------------------------

    def summary(self):

        return {

            "logged_in": self.logged_in,

            "orders": len(self.orders),

            "positions": len(self.positions),

            "holdings": len(self.holdings),

            "trades": len(self.trade_history),

            "available_balance": self.funds["available_balance"],

            "used_margin": self.funds["used_margin"],

            "realized_pnl": self.funds["realized_pnl"],

            "unrealized_pnl": self.funds["unrealized_pnl"],

        }