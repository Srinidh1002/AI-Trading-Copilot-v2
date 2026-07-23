"""
Snapshot Database

Persistent storage for market snapshots.

Responsibilities
----------------
✓ Create Snapshot Table
✓ Save Market Snapshots
✓ Update Snapshots
✓ Delete Snapshots
✓ Fetch Snapshots
✓ Latest Snapshot
✓ Symbol-wise History
✓ Snapshot Statistics
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from services.database.database_manager import DatabaseManager


class SnapshotDatabase:

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
            CREATE TABLE IF NOT EXISTS market_snapshots (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                symbol TEXT NOT NULL,

                timeframe TEXT,

                price REAL,

                open REAL,

                high REAL,

                low REAL,

                close REAL,

                volume REAL,

                market_score REAL,

                bull_score REAL,

                bear_score REAL,

                trend TEXT,

                recommendation TEXT,

                confidence REAL,

                snapshot_time TEXT,

                metadata TEXT

            )
            """
        )

    # --------------------------------------------------

    def insert_snapshot(
        self,
        symbol: str,
        timeframe: str,
        price: float,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: float,
        market_score: float = 0.0,
        bull_score: float = 0.0,
        bear_score: float = 0.0,
        trend: str | None = None,
        recommendation: str | None = None,
        confidence: float | None = None,
        metadata: str | None = None,
    ) -> int:

        cursor = self.db.execute(
            """
            INSERT INTO market_snapshots (

                symbol,
                timeframe,
                price,
                open,
                high,
                low,
                close,
                volume,
                market_score,
                bull_score,
                bear_score,
                trend,
                recommendation,
                confidence,
                snapshot_time,
                metadata

            )

            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                symbol,
                timeframe,
                price,
                open_price,
                high,
                low,
                close,
                volume,
                market_score,
                bull_score,
                bear_score,
                trend,
                recommendation,
                confidence,
                datetime.now().isoformat(),
                metadata,
            ),
        )

        return cursor.lastrowid

    # --------------------------------------------------

    def update_snapshot(
        self,
        snapshot_id: int,
        **fields: Any,
    ):

        if not fields:
            return

        columns = ", ".join(
            f"{key}=?"
            for key in fields
        )

        values = list(fields.values())

        values.append(snapshot_id)

        self.db.execute(
            f"""
            UPDATE market_snapshots

            SET {columns}

            WHERE id=?
            """,
            tuple(values),
        )

    # --------------------------------------------------

    def delete_snapshot(
        self,
        snapshot_id: int,
    ):

        self.db.execute(
            """
            DELETE FROM market_snapshots
            WHERE id=?
            """,
            (snapshot_id,),
        )

    # --------------------------------------------------

    def get_snapshot(
        self,
        snapshot_id: int,
    ) -> dict[str, Any] | None:

        return self.db.fetch_one(
            """
            SELECT *
            FROM market_snapshots
            WHERE id=?
            """,
            (snapshot_id,),
        )

    # --------------------------------------------------

    def latest_snapshot(
        self,
        symbol: str,
    ) -> dict[str, Any] | None:

        return self.db.fetch_one(
            """
            SELECT *
            FROM market_snapshots

            WHERE symbol=?

            ORDER BY id DESC

            LIMIT 1
            """,
            (symbol,),
        )

    # --------------------------------------------------

    def history(
        self,
        symbol: str,
        limit: int = 100,
    ):

        return self.db.fetch_all(
            """
            SELECT *

            FROM market_snapshots

            WHERE symbol=?

            ORDER BY id DESC

            LIMIT ?
            """,
            (
                symbol,
                limit,
            ),
        )

    # --------------------------------------------------

    def all_snapshots(self):

        return self.db.fetch_all(
            """
            SELECT *

            FROM market_snapshots

            ORDER BY id DESC
            """
        )

    # --------------------------------------------------

    def total_snapshots(self) -> int:

        row = self.db.fetch_one(
            """
            SELECT COUNT(*) AS total

            FROM market_snapshots
            """
        )

        return row["total"]

    # --------------------------------------------------

    def symbols(self):

        rows = self.db.fetch_all(
            """
            SELECT DISTINCT symbol

            FROM market_snapshots

            ORDER BY symbol
            """
        )

        return [

            row["symbol"]

            for row in rows

        ]

    # --------------------------------------------------

    def summary(self):

        return {

            "total_snapshots": self.total_snapshots(),

            "symbols": self.symbols(),

        }