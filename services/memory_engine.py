"""
Memory Engine

Provides persistent storage for the AI Trading Copilot.
Trade history is automatically saved and loaded between sessions.
"""

import json
from pathlib import Path
from typing import Dict, List


MEMORY_FILE = Path("database/trade_memory.json")


class MemoryEngine:

    def __init__(self):

        MEMORY_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.trade_history = self.load()

    def load(self) -> List[Dict]:

        if not MEMORY_FILE.exists():
            return []

        try:

            with open(
                MEMORY_FILE,
                "r",
                encoding="utf-8",
            ) as file:

                return json.load(file)

        except Exception:

            return []

    def save(self) -> None:

        with open(
            MEMORY_FILE,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                self.trade_history,
                file,
                indent=4,
            )

    def add_trade(
        self,
        trade: Dict,
    ) -> None:

        self.trade_history.append(
            trade
        )

        self.save()

    def get_all_trades(
        self,
    ) -> List[Dict]:

        return self.trade_history

    def clear(self) -> None:

        self.trade_history = []

        self.save()

    def total_trades(
        self,
    ) -> int:

        return len(
            self.trade_history
        )


memory_engine = MemoryEngine()