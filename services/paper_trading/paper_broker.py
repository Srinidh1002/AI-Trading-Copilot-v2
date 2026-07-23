"""
Paper Broker

Simulates a real broker.

Responsibilities
----------------
✓ Accept orders
✓ Generate order IDs
✓ Simulate fills
✓ Maintain positions
✓ Maintain order history
✓ Return broker-like responses
"""

from __future__ import annotations

import uuid
from datetime import datetime


class PaperBroker:

    def __init__(self):

        self.orders = {}

        self.positions = {}

    # --------------------------------------------------

    def place_order(
        self,
        order: dict,
    ):

        order_id = str(uuid.uuid4())

        response = {

            "success": True,

            "broker": "Paper",

            "order_id": order_id,

            "status": "FILLED",

            "message": "Paper order executed.",

            "filled_qty": order["quantity"],

            "timestamp": datetime.now(),

        }

        self.orders[order_id] = {

            **order,

            **response,

        }

        symbol = order["symbol"]

        qty = order["quantity"]

        signal = order["signal"]

        current = self.positions.get(symbol, 0)

        if signal == "BUY":

            current += qty

        elif signal == "SELL":

            current -= qty

        self.positions[symbol] = current

        return response

    # --------------------------------------------------

    def cancel_order(
        self,
        order_id,
    ):

        if order_id not in self.orders:

            return False

        self.orders[order_id]["status"] = "CANCELLED"

        return True

    # --------------------------------------------------

    def get_order(
        self,
        order_id,
    ):

        return self.orders.get(order_id)

    # --------------------------------------------------

    def get_positions(
        self,
    ):

        return dict(self.positions)

    # --------------------------------------------------

    def order_history(
        self,
    ):

        return dict(self.orders)

    # --------------------------------------------------

    def reset(
        self,
    ):

        self.orders.clear()

        self.positions.clear()