"""
Alert Dispatcher

Routes notifications to one or more delivery channels.

Responsibilities
----------------
✓ Console Alerts
✓ Log Alerts
✓ Notification Manager Integration
✓ Multi-channel Dispatch
✓ Broadcast Messages
"""

from __future__ import annotations

import logging
from typing import Any

from services.notifications.notification_manager import (
    NotificationManager,
)


class AlertDispatcher:

    def __init__(
        self,
        notification_manager: NotificationManager | None = None,
    ):

        self.manager = (
            notification_manager
            if notification_manager
            else NotificationManager()
        )

        self.logger = logging.getLogger(
            "AlertDispatcher"
        )

    # --------------------------------------------------

    def dispatch_info(
        self,
        title: str,
        message: str,
        data: dict[str, Any] | None = None,
    ):

        notification = self.manager.info(
            title,
            message,
            data,
        )

        self.logger.info(
            "%s - %s",
            title,
            message,
        )

        print(
            f"[INFO] {title}: {message}"
        )

        return notification

    # --------------------------------------------------

    def dispatch_success(
        self,
        title: str,
        message: str,
        data: dict[str, Any] | None = None,
    ):

        notification = self.manager.success(
            title,
            message,
            data,
        )

        self.logger.info(
            "%s - %s",
            title,
            message,
        )

        print(
            f"[SUCCESS] {title}: {message}"
        )

        return notification

    # --------------------------------------------------

    def dispatch_warning(
        self,
        title: str,
        message: str,
        data: dict[str, Any] | None = None,
    ):

        notification = self.manager.warning(
            title,
            message,
            data,
        )

        self.logger.warning(
            "%s - %s",
            title,
            message,
        )

        print(
            f"[WARNING] {title}: {message}"
        )

        return notification

    # --------------------------------------------------

    def dispatch_error(
        self,
        title: str,
        message: str,
        data: dict[str, Any] | None = None,
    ):

        notification = self.manager.error(
            title,
            message,
            data,
        )

        self.logger.error(
            "%s - %s",
            title,
            message,
        )

        print(
            f"[ERROR] {title}: {message}"
        )

        return notification

    # --------------------------------------------------

    def dispatch_trade(
        self,
        symbol: str,
        signal: str,
        confidence: float,
    ):

        notification = self.manager.trade_alert(
            symbol,
            signal,
            confidence,
        )

        self.logger.info(
            "Trade Alert: %s %s %.2f%%",
            symbol,
            signal,
            confidence,
        )

        print(
            f"[TRADE] {symbol} | {signal} | {confidence:.2f}%"
        )

        return notification

    # --------------------------------------------------

    def dispatch_order(
        self,
        order_id: str,
        status: str,
    ):

        notification = self.manager.order_update(
            order_id,
            status,
        )

        self.logger.info(
            "Order %s -> %s",
            order_id,
            status,
        )

        print(
            f"[ORDER] {order_id} -> {status}"
        )

        return notification

    # --------------------------------------------------

    def dispatch_risk(
        self,
        reason: str,
    ):

        notification = self.manager.risk_alert(
            reason,
        )

        self.logger.warning(
            "Risk Alert: %s",
            reason,
        )

        print(
            f"[RISK] {reason}"
        )

        return notification

    # --------------------------------------------------

    def broadcast(
        self,
        title: str,
        message: str,
        level: str = "INFO",
    ):

        level = level.upper()

        if level == "SUCCESS":

            return self.dispatch_success(
                title,
                message,
            )

        if level == "WARNING":

            return self.dispatch_warning(
                title,
                message,
            )

        if level == "ERROR":

            return self.dispatch_error(
                title,
                message,
            )

        return self.dispatch_info(
            title,
            message,
        )

    # --------------------------------------------------

    def history(self):

        return self.manager.all_notifications()

    # --------------------------------------------------

    def summary(self):

        return self.manager.summary()

    # --------------------------------------------------

    def clear(self):

        self.manager.clear()