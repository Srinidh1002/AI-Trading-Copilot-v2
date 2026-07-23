"""
Trade Database

Persistent trade storage built on top of
DatabaseManager.

Responsibilities
----------------
✓ Create Trade Table
✓ Insert Trades
✓ Update Trades
✓ Delete Trades
✓ Fetch Trades
✓ Trade Statistics
✓ Export-ready Data Access
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from services.database.database_manager import DatabaseManager


class TradeDatabase:

    def __init__(
        self,
        database: DatabaseManager | None = None,
    ):

        self.db = database or DatabaseManager()

        self._create_table()

    # --------------------------------------------------

    def _create_table(self):

        self.db.create_table(
            """
            CREATE TABLE IF NOT EXISTS trades (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                symbol TEXT NOT NULL,

                side TEXT NOT NULL,

                quantity REAL NOT NULL,

                entry_price REAL NOT NULL,

                exit_price REAL,

                stop_loss REAL,

                target REAL,

                pnl REAL,

                status TEXT,

                strategy TEXT,

                confidence REAL,

                entry_time TEXT,

                exit_time TEXT,

                remarks TEXT

            )
            """
        )

    # --------------------------------------------------

    def insert_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        stop_loss: float | None = None,
        target: float | None = None,
        strategy: str | None = None,
        confidence: float | None = None,
        remarks: str | None = None,
    ) -> int:

        cursor = self.db.execute(
            """
            INSERT INTO trades (

                symbol,
                side,
                quantity,
                entry_price,
                stop_loss,
                target,
                pnl,
                status,
                strategy,
                confidence,
                entry_time,
                remarks

            )

            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                symbol,
                side,
                quantity,
                entry_price,
                stop_loss,
                target,
                0.0,
                "OPEN",
                strategy,
                confidence,
                datetime.now().isoformat(),
                remarks,
            ),
        )

        return cursor.lastrowid

    # --------------------------------------------------

    def close_trade(
        self,
        trade_id: int,
        exit_price: float,
        pnl: float,
    ):

        self.db.execute(
            """
            UPDATE trades

            SET

                exit_price=?,
                pnl=?,
                status='CLOSED',
                exit_time=?

            WHERE id=?
            """,
            (
                exit_price,
                pnl,
                datetime.now().isoformat(),
                trade_id,
            ),
        )

    # --------------------------------------------------

    def update_trade(
        self,
        trade_id: int,
        **fields: Any,
    ):

        if not fields:
            return

        columns = ", ".join(
            f"{key}=?"
            for key in fields
        )

        values = list(fields.values())

        values.append(trade_id)

        self.db.execute(
            f"""
            UPDATE trades

            SET {columns}

            WHERE id=?
            """,
            tuple(values),
        )

    # --------------------------------------------------

    def delete_trade(
        self,
        trade_id: int,
    ):

        self.db.execute(
            """
            DELETE FROM trades
            WHERE id=?
            """,
            (trade_id,),
        )

    # --------------------------------------------------

    def get_trade(
        self,
        trade_id: int,
    ) -> dict[str, Any] | None:

        return self.db.fetch_one(
            """
            SELECT *
            FROM trades
            WHERE id=?
            """,
            (trade_id,),
        )

    # --------------------------------------------------

    def get_all_trades(self):

        return self.db.fetch_all(
            """
            SELECT *
            FROM trades
            ORDER BY id DESC
            """
        )

    # --------------------------------------------------

    def get_open_trades(self):

        return self.db.fetch_all(
            """
            SELECT *
            FROM trades
            WHERE status='OPEN'
            ORDER BY id DESC
            """
        )

    # --------------------------------------------------

    def get_closed_trades(self):

        return self.db.fetch_all(
            """
            SELECT *
            FROM trades
            WHERE status='CLOSED'
            ORDER BY id DESC
            """
        )

    # --------------------------------------------------

    def get_trades_by_symbol(
        self,
        symbol: str,
    ):

        return self.db.fetch_all(
            """
            SELECT *
            FROM trades
            WHERE symbol=?
            ORDER BY id DESC
            """,
            (symbol,),
        )

    # --------------------------------------------------

    def total_trades(self) -> int:

        row = self.db.fetch_one(
            """
            SELECT COUNT(*) AS total
            FROM trades
            """
        )

        return row["total"]

    # --------------------------------------------------

    def open_trade_count(self) -> int:

        row = self.db.fetch_one(
            """
            SELECT COUNT(*) AS total
            FROM trades
            WHERE status='OPEN'
            """
        )

        return row["total"]

    # --------------------------------------------------

    def closed_trade_count(self) -> int:

        row = self.db.fetch_one(
            """
            SELECT COUNT(*) AS total
            FROM trades
            WHERE status='CLOSED'
            """
        )

        return row["total"]

    # --------------------------------------------------

    def total_pnl(self) -> float:

        row = self.db.fetch_one(
            """
            SELECT COALESCE(SUM(pnl),0) AS pnl
            FROM trades
            """
        )

        return float(row["pnl"])

    # --------------------------------------------------

    def summary(self):

        return {

            "total_trades": self.total_trades(),

            "open_trades": self.open_trade_count(),

            "closed_trades": self.closed_trade_count(),

            "total_pnl": self.total_pnl(),

        }