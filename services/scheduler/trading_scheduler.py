"""
Trading Scheduler

Central scheduler for the AI Trading Copilot.

Responsibilities
----------------
✓ Market Session Control
✓ Periodic Strategy Execution
✓ Pre-Market Tasks
✓ Live Market Tasks
✓ Post-Market Tasks
✓ Heartbeat Monitoring
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Callable, Any


class TradingScheduler:

    def __init__(self):

        self.tasks: list[dict[str, Any]] = []

        self.running = False

    # --------------------------------------------------

    def add_task(
        self,
        name: str,
        callback: Callable,
        interval_seconds: int,
    ):

        self.tasks.append(

            {

                "name": name,

                "callback": callback,

                "interval": interval_seconds,

                "last_run": 0.0,

            }

        )

    # --------------------------------------------------

    def remove_task(
        self,
        name: str,
    ):

        self.tasks = [

            task

            for task in self.tasks

            if task["name"] != name

        ]

    # --------------------------------------------------

    def run_pending(
        self,
    ):

        current_time = time.time()

        for task in self.tasks:

            if (

                current_time - task["last_run"]

                >= task["interval"]

            ):

                try:

                    task["callback"]()

                    task["last_run"] = current_time

                except Exception as exc:

                    print(

                        f"[Scheduler] "

                        f"{task['name']} failed: {exc}"

                    )

    # --------------------------------------------------

    def start(
        self,
        sleep_interval: float = 1.0,
    ):

        self.running = True

        while self.running:

            self.run_pending()

            time.sleep(
                sleep_interval
            )

    # --------------------------------------------------

    def stop(
        self,
    ):

        self.running = False

    # --------------------------------------------------

    @staticmethod
    def market_is_open() -> bool:

        now = datetime.now()

        if now.weekday() >= 5:

            return False

        current = now.hour * 60 + now.minute

        market_open = 9 * 60 + 15

        market_close = 15 * 60 + 30

        return market_open <= current <= market_close

    # --------------------------------------------------

    def summary(
        self,
    ):

        return {

            "running": self.running,

            "market_open": self.market_is_open(),

            "registered_tasks": len(

                self.tasks

            ),

            "tasks": [

                {

                    "name": task["name"],

                    "interval": task["interval"],

                }

                for task in self.tasks

            ],

        }

    # --------------------------------------------------

    def clear(
        self,
    ):

        self.tasks.clear()

        self.running = False