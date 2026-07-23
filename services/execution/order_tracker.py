"""
Order Tracker

Tracks the lifecycle of broker orders.

Responsibilities
----------------
✓ Track order status
✓ Update active orders
✓ Remove completed orders
✓ Maintain execution history
✓ Provide order lookup

Does NOT
--------
✗ Place orders
✗ Validate trades
✗ Calculate risk
✗ Modify orders
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

LOGGER = logging.getLogger(__name__)


class OrderTracker:

    def __init__(self):

        self.orders: dict[str, dict[str, Any]] = {}

        self.completed_orders: dict[str, dict[str, Any]] = {}

    # --------------------------------------------------

    def register(
        self,
        order_id: str,
        order_data: dict[str, Any],
    ):

        self.orders[order_id] = {

            **order_data,

            "status": "PENDING",

            "created_at": datetime.now(),

            "updated_at": datetime.now(),

        }

        LOGGER.info(
            "Registered order %s",
            order_id,
        )

    # --------------------------------------------------

    def update_status(
        self,
        order_id: str,
        status: str,
        **extra,
    ):

        if order_id not in self.orders:
            return

        self.orders[order_id]["status"] = status

        self.orders[order_id]["updated_at"] = datetime.now()

        self.orders[order_id].update(extra)

        LOGGER.info(
            "Order %s -> %s",
            order_id,
            status,
        )

        if status.upper() in {

            "FILLED",

            "CANCELLED",

            "REJECTED",

            "EXPIRED",

        }:

            self.completed_orders[order_id] = self.orders.pop(order_id)

    # --------------------------------------------------

    def get(
        self,
        order_id: str,
    ) -> dict[str, Any] | None:

        if order_id in self.orders:
            return self.orders[order_id]

        return self.completed_orders.get(order_id)

    # --------------------------------------------------

    def is_active(
        self,
        order_id: str,
    ) -> bool:

        return order_id in self.orders

    # --------------------------------------------------

    def active_orders(self):

        return dict(self.orders)

    # --------------------------------------------------

    def completed(self):

        return dict(self.completed_orders)

    # --------------------------------------------------

    def active_count(self):

        return len(self.orders)

    # --------------------------------------------------

    def completed_count(self):

        return len(self.completed_orders)

    # --------------------------------------------------

    def summary(self):

        return {

            "active_orders": len(self.orders),

            "completed_orders": len(self.completed_orders),

        }

    # --------------------------------------------------

    def clear_completed(self):

        self.completed_orders.clear()

        LOGGER.info(
            "Completed order history cleared."
        )