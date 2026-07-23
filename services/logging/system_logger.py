"""
System Logger

Centralized logging utility for the
AI Trading Copilot.

Responsibilities
----------------
✓ Application Logs
✓ Trade Logs
✓ Error Logs
✓ Risk Logs
✓ Execution Logs
✓ AI Decision Logs
✓ Daily Log Files
"""

from __future__ import annotations

import logging
from pathlib import Path
from datetime import datetime


class SystemLogger:

    def __init__(
        self,
        log_directory: str = "logs",
        logger_name: str = "AITradingCopilot",
    ):

        self.log_directory = Path(log_directory)

        self.log_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        log_file = self.log_directory / (
            datetime.now().strftime("%Y-%m-%d") + ".log"
        )

        self.logger = logging.getLogger(
            logger_name
        )

        self.logger.setLevel(
            logging.INFO
        )

        if not self.logger.handlers:

            formatter = logging.Formatter(

                "%(asctime)s | %(levelname)s | %(message)s"

            )

            file_handler = logging.FileHandler(
                log_file,
                encoding="utf-8",
            )

            file_handler.setFormatter(
                formatter
            )

            console_handler = logging.StreamHandler()

            console_handler.setFormatter(
                formatter
            )

            self.logger.addHandler(
                file_handler
            )

            self.logger.addHandler(
                console_handler
            )

    # --------------------------------------------------

    def info(
        self,
        message: str,
    ):

        self.logger.info(
            message
        )

    # --------------------------------------------------

    def warning(
        self,
        message: str,
    ):

        self.logger.warning(
            message
        )

    # --------------------------------------------------

    def error(
        self,
        message: str,
    ):

        self.logger.error(
            message
        )

    # --------------------------------------------------

    def critical(
        self,
        message: str,
    ):

        self.logger.critical(
            message
        )

    # --------------------------------------------------

    def trade(
        self,
        symbol: str,
        signal: str,
        quantity: int,
        price: float,
    ):

        self.logger.info(

            "[TRADE] "

            f"{symbol} | "

            f"{signal} | "

            f"Qty={quantity} | "

            f"Price={price}"

        )

    # --------------------------------------------------

    def order(
        self,
        order_id: str,
        status: str,
    ):

        self.logger.info(

            "[ORDER] "

            f"{order_id} -> {status}"

        )

    # --------------------------------------------------

    def risk(
        self,
        message: str,
    ):

        self.logger.warning(

            "[RISK] "

            f"{message}"

        )

    # --------------------------------------------------

    def ai_decision(
        self,
        signal: str,
        confidence: float,
    ):

        self.logger.info(

            "[AI] "

            f"{signal} "

            f"({confidence:.2f}%)"

        )

    # --------------------------------------------------

    def exception(
        self,
        message: str,
    ):

        self.logger.exception(
            message
        )

    # --------------------------------------------------

    def shutdown(
        self,
    ):

        logging.shutdown()