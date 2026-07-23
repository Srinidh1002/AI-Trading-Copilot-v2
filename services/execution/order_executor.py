"""
Order Executor

Executes validated orders through the configured broker.

Responsibilities
----------------
✓ Execute approved orders
✓ Standardize broker responses
✓ Retry transient failures
✓ Log execution attempts

Does NOT:
-----------
✗ Generate trading signals
✗ Validate trades
✗ Calculate risk
✗ Check market conditions
"""

from __future__ import annotations

import logging
import time
from typing import Any

from services.broker.session_manager import SessionManager

LOGGER = logging.getLogger(__name__)


class OrderExecutor:
    """
    Broker-independent execution engine.
    """

    def __init__(
        self,
        broker_name: str = "Angel",
        max_retries: int = 2,
        retry_delay: float = 1.0,
    ):

        self.broker_name = broker_name
        self.max_retries = max(0, int(max_retries))
        self.retry_delay = max(0.0, float(retry_delay))

        self.session = SessionManager()

    # -----------------------------------------------------

    def execute(
        self,
        order: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute a validated order.

        Expected order format:

        {
            "symbol": "...",
            "signal": "BUY",
            "quantity": 75,
            "order_type": "MARKET",
            "product": "INTRADAY",
            "price": None,
        }
        """

        self._validate_order(order)

        attempt = 0

        while True:

            try:

                response = self._place_order(order)

                return self._standardize_response(
                    response=response,
                    success=True,
                )

            except Exception as exc:

                LOGGER.exception(
                    "Order execution failed."
                )

                attempt += 1

                if attempt > self.max_retries:

                    return self._standardize_response(
                        response={
                            "message": str(exc),
                        },
                        success=False,
                    )

                time.sleep(self.retry_delay)

    # -----------------------------------------------------

    def _place_order(
        self,
        order: dict[str, Any],
    ):
        """
        Placeholder broker execution.

        Replace this method with your
        broker's place_order() call.
        """

        api = self.session.api

        raise NotImplementedError(
            "Connect this method to the broker "
            "place_order API."
        )

    # -----------------------------------------------------

    @staticmethod
    def _validate_order(
        order: dict[str, Any],
    ):

        required = (
            "symbol",
            "signal",
            "quantity",
            "order_type",
            "product",
        )

        for field in required:

            if field not in order:

                raise ValueError(
                    f"Missing field: {field}"
                )

        if order["quantity"] <= 0:

            raise ValueError(
                "Quantity must be greater than zero."
            )

    # -----------------------------------------------------

    def _standardize_response(
        self,
        *,
        response,
        success: bool,
    ):

        if success:

            return {

                "success": True,

                "broker": self.broker_name,

                "order_id": response.get(
                    "order_id"
                ),

                "status": response.get(
                    "status",
                    "UNKNOWN",
                ),

                "message": response.get(
                    "message",
                    "",
                ),

                "raw_response": response,

            }

        return {

            "success": False,

            "broker": self.broker_name,

            "order_id": None,

            "status": "FAILED",

            "message": response.get(
                "message",
                "Unknown error",
            ),

            "raw_response": response,

        }