"""
Test Data Generator

Generates realistic mock datasets for testing the
AI Trading Copilot.

Responsibilities
----------------
✓ Market Snapshot Generator
✓ OHLC Data Generator
✓ Trade Generator
✓ Position Generator
✓ Portfolio Generator
✓ Option Chain Generator
✓ Watchlist Generator
✓ Export Test Data
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd


class TestDataGenerator:

    def __init__(self, seed: int = 42):

        random.seed(seed)

    # --------------------------------------------------

    def market_snapshot(self) -> dict[str, Any]:

        price = round(

            random.uniform(24000, 25500),

            2,

        )

        return {

            "symbol": "^NSEI",

            "timestamp": datetime.now().isoformat(),

            "price": price,

            "open": round(price - random.uniform(20, 120), 2),

            "high": round(price + random.uniform(10, 180), 2),

            "low": round(price - random.uniform(10, 180), 2),

            "volume": random.randint(

                1_000_000,

                50_000_000,

            ),

            "trend": random.choice(

                [

                    "Bullish",

                    "Bearish",

                    "Sideways",

                ]

            ),

        }

    # --------------------------------------------------

    def ohlc_data(

        self,

        periods: int = 200,

        start_price: float = 25000,

    ) -> pd.DataFrame:

        rows = []

        current = start_price

        start = datetime.now() - timedelta(

            minutes=periods

        )

        for i in range(periods):

            open_price = current

            close = open_price + random.uniform(

                -80,

                80,

            )

            high = max(

                open_price,

                close,

            ) + random.uniform(

                0,

                35,

            )

            low = min(

                open_price,

                close,

            ) - random.uniform(

                0,

                35,

            )

            volume = random.randint(

                20000,

                500000,

            )

            rows.append(

                {

                    "datetime": start + timedelta(

                        minutes=i,

                    ),

                    "open": round(open_price, 2),

                    "high": round(high, 2),

                    "low": round(low, 2),

                    "close": round(close, 2),

                    "volume": volume,

                }

            )

            current = close

        return pd.DataFrame(rows)

    # --------------------------------------------------

    def trade(self) -> dict[str, Any]:

        side = random.choice(

            [

                "BUY",

                "SELL",

            ]

        )

        qty = random.randint(

            25,

            300,

        )

        entry = round(

            random.uniform(100, 450),

            2,

        )

        exit_price = round(

            entry + random.uniform(

                -35,

                45,

            ),

            2,

        )

        pnl = round(

            (exit_price - entry)

            * qty

            * (1 if side == "BUY" else -1),

            2,

        )

        return {

            "trade_id": random.randint(

                100000,

                999999,

            ),

            "symbol": random.choice(

                [

                    "NIFTY",

                    "BANKNIFTY",

                    "SENSEX",

                ]

            ),

            "side": side,

            "quantity": qty,

            "entry_price": entry,

            "exit_price": exit_price,

            "pnl": pnl,

            "status": random.choice(

                [

                    "OPEN",

                    "CLOSED",

                ]

            ),

        }

    # --------------------------------------------------

    def trades(

        self,

        count: int = 100,

    ) -> list[dict[str, Any]]:

        return [

            self.trade()

            for _ in range(count)

        ]

    # --------------------------------------------------

    def position(self) -> dict[str, Any]:

        qty = random.randint(

            25,

            300,

        )

        avg = round(

            random.uniform(

                150,

                450,

            ),

            2,

        )

        ltp = round(

            avg + random.uniform(

                -40,

                40,

            ),

            2,

        )

        pnl = round(

            (ltp - avg) * qty,

            2,

        )

        return {

            "symbol": random.choice(

                [

                    "NIFTY",

                    "BANKNIFTY",

                    "SENSEX",

                ]

            ),

            "quantity": qty,

            "average_price": avg,

            "ltp": ltp,

            "unrealized_pnl": pnl,

        }

    # --------------------------------------------------

    def portfolio(

        self,

        positions: int = 8,

    ) -> dict[str, Any]:

        data = [

            self.position()

            for _ in range(positions)

        ]

        total = sum(

            item["unrealized_pnl"]

            for item in data

        )

        return {

            "positions": data,

            "total_positions": len(data),

            "portfolio_pnl": round(

                total,

                2,

            ),

        }

    # --------------------------------------------------

    def option_chain(

        self,

        strike_count: int = 15,

    ) -> list[dict[str, Any]]:

        atm = random.randrange(

            24500,

            25500,

            50,

        )

        chain = []

        for strike in range(

            atm - strike_count * 50,

            atm + strike_count * 50 + 50,

            50,

        ):

            chain.append(

                {

                    "strike": strike,

                    "call_oi": random.randint(

                        500,

                        20000,

                    ),

                    "put_oi": random.randint(

                        500,

                        20000,

                    ),

                    "call_ltp": round(

                        random.uniform(

                            2,

                            350,

                        ),

                        2,

                    ),

                    "put_ltp": round(

                        random.uniform(

                            2,

                            350,

                        ),

                        2,

                    ),

                }

            )

        return chain

    # --------------------------------------------------

    def watchlist(self) -> list[dict[str, Any]]:

        symbols = [

            "^NSEI",

            "^NSEBANK",

            "^BSESN",

            "RELIANCE.NS",

            "TCS.NS",

            "INFY.NS",

            "HDFCBANK.NS",

            "ICICIBANK.NS",

        ]

        data = []

        for symbol in symbols:

            change = round(

                random.uniform(

                    -3,

                    3,

                ),

                2,

            )

            data.append(

                {

                    "symbol": symbol,

                    "ltp": round(

                        random.uniform(

                            100,

                            50000,

                        ),

                        2,

                    ),

                    "change_percent": change,

                    "trend": (

                        "Bullish"

                        if change > 0

                        else "Bearish"

                    ),

                }

            )

        return data

    # --------------------------------------------------

    def export_json(

        self,

        data: Any,

        filename: str,

    ) -> str:

        path = Path(filename)

        path.parent.mkdir(

            parents=True,

            exist_ok=True,

        )

        with open(

            path,

            "w",

            encoding="utf-8",

        ) as file:

            json.dump(

                data,

                file,

                indent=4,

                default=str,

            )

        return str(path)

    # --------------------------------------------------

    def export_csv(

        self,

        dataframe: pd.DataFrame,

        filename: str,

    ) -> str:

        path = Path(filename)

        path.parent.mkdir(

            parents=True,

            exist_ok=True,

        )

        dataframe.to_csv(

            path,

            index=False,

        )

        return str(path)

    # --------------------------------------------------

    def generate_all(self) -> dict[str, Any]:

        return {

            "market_snapshot": self.market_snapshot(),

            "ohlc": self.ohlc_data(),

            "trades": self.trades(100),

            "portfolio": self.portfolio(),

            "option_chain": self.option_chain(),

            "watchlist": self.watchlist(),

        }