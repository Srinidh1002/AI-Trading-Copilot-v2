"""
Audit Logger

Maintains an immutable audit trail for all
critical trading system events.

Responsibilities
----------------
✓ User Actions
✓ Trade Decisions
✓ Order Lifecycle
✓ Risk Events
✓ System Events
✓ Security Events
✓ Persistent Audit Log
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Any


class AuditLogger:

    def __init__(
        self,
        audit_directory: str = "logs/audit",
    ):

        self.audit_directory = Path(
            audit_directory
        )

        self.audit_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.audit_file = (
            self.audit_directory
            / (
                datetime.now().strftime(
                    "%Y-%m-%d"
                )
                + "_audit.jsonl"
            )
        )

    # --------------------------------------------------

    def log_event(
        self,
        event_type: str,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        event = {

            "timestamp": datetime.now().isoformat(),

            "event_type": event_type.upper(),

            "message": message,

            "data": data or {},

        }

        with self.audit_file.open(
            "a",
            encoding="utf-8",
        ) as file:

            file.write(
                json.dumps(
                    event,
                    default=str,
                )
            )

            file.write("\n")

        return event

    # --------------------------------------------------

    def trade_event(
        self,
        symbol: str,
        signal: str,
        quantity: int,
        price: float,
    ):

        return self.log_event(

            "TRADE",

            f"{signal.upper()} {symbol}",

            {

                "symbol": symbol,

                "signal": signal,

                "quantity": quantity,

                "price": price,

            },

        )

    # --------------------------------------------------

    def order_event(
        self,
        order_id: str,
        status: str,
    ):

        return self.log_event(

            "ORDER",

            f"Order {order_id} -> {status}",

            {

                "order_id": order_id,

                "status": status,

            },

        )

    # --------------------------------------------------

    def risk_event(
        self,
        reason: str,
    ):

        return self.log_event(

            "RISK",

            reason,

        )

    # --------------------------------------------------

    def system_event(
        self,
        message: str,
    ):

        return self.log_event(

            "SYSTEM",

            message,

        )

    # --------------------------------------------------

    def security_event(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ):

        return self.log_event(

            "SECURITY",

            message,

            details,

        )

    # --------------------------------------------------

    def ai_decision(
        self,
        signal: str,
        confidence: float,
        reasoning: str | None = None,
    ):

        return self.log_event(

            "AI_DECISION",

            f"{signal.upper()} ({confidence:.2f}%)",

            {

                "signal": signal,

                "confidence": confidence,

                "reasoning": reasoning,

            },

        )

    # --------------------------------------------------

    def custom_event(
        self,
        event_type: str,
        message: str,
        data: dict[str, Any] | None = None,
    ):

        return self.log_event(

            event_type,

            message,

            data,

        )

    # --------------------------------------------------

    def log_exception(
        self,
        exception: Exception,
        context: str = "",
    ):

        return self.log_event(

            "EXCEPTION",

            str(exception),

            {

                "context": context,

                "exception_type": type(exception).__name__,

            },

        )

    # --------------------------------------------------

    def audit_file_path(
        self,
    ) -> str:

        return str(self.audit_file)