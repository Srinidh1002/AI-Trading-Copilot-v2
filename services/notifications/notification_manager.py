"""
Notification Manager

Central notification service for the
AI Trading Copilot.

Responsibilities
----------------
✓ Trade Alerts
✓ Order Updates
✓ Risk Alerts
✓ System Notifications
✓ Warning Messages
✓ Error Notifications
✓ Event History
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


class NotificationManager:

    def __init__(self):

        self.notifications: list[dict[str, Any]] = []

    # --------------------------------------------------

    def _create_notification(
        self,
        level: str,
        title: str,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        notification = {

            "timestamp": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

            "level": level.upper(),

            "title": title,

            "message": message,

            "data": data or {},

        }

        self.notifications.append(notification)

        return notification

    # --------------------------------------------------

    def info(
        self,
        title: str,
        message: str,
        data: dict[str, Any] | None = None,
    ):

        return self._create_notification(
            "INFO",
            title,
            message,
            data,
        )

    # --------------------------------------------------

    def success(
        self,
        title: str,
        message: str,
        data: dict[str, Any] | None = None,
    ):

        return self._create_notification(
            "SUCCESS",
            title,
            message,
            data,
        )

    # --------------------------------------------------

    def warning(
        self,
        title: str,
        message: str,
        data: dict[str, Any] | None = None,
    ):

        return self._create_notification(
            "WARNING",
            title,
            message,
            data,
        )

    # --------------------------------------------------

    def error(
        self,
        title: str,
        message: str,
        data: dict[str, Any] | None = None,
    ):

        return self._create_notification(
            "ERROR",
            title,
            message,
            data,
        )

    # --------------------------------------------------

    def trade_alert(
        self,
        symbol: str,
        signal: str,
        confidence: float,
    ):

        return self.success(

            title="Trade Alert",

            message=(
                f"{signal.upper()} signal generated "
                f"for {symbol} "
                f"(Confidence: {confidence:.2f}%)"
            ),

            data={

                "symbol": symbol,

                "signal": signal,

                "confidence": confidence,

            },

        )

    # --------------------------------------------------

    def order_update(
        self,
        order_id: str,
        status: str,
    ):

        return self.info(

            title="Order Update",

            message=f"Order {order_id} is {status}.",

            data={

                "order_id": order_id,

                "status": status,

            },

        )

    # --------------------------------------------------

    def risk_alert(
        self,
        reason: str,
    ):

        return self.warning(

            title="Risk Alert",

            message=reason,

        )

    # --------------------------------------------------

    def system_alert(
        self,
        message: str,
    ):

        return self.info(

            title="System",

            message=message,

        )

    # --------------------------------------------------

    def latest(
        self,
        limit: int = 20,
    ):

        return self.notifications[-limit:]

    # --------------------------------------------------

    def all_notifications(
        self,
    ):

        return self.notifications

    # --------------------------------------------------

    def clear(
        self,
    ):

        self.notifications.clear()

    # --------------------------------------------------

    def summary(
        self,
    ):

        counts = {

            "INFO": 0,

            "SUCCESS": 0,

            "WARNING": 0,

            "ERROR": 0,

        }

        for notification in self.notifications:

            level = notification["level"]

            counts[level] = counts.get(level, 0) + 1

        return {

            "total_notifications": len(self.notifications),

            "info": counts["INFO"],

            "success": counts["SUCCESS"],

            "warning": counts["WARNING"],

            "error": counts["ERROR"],

        }