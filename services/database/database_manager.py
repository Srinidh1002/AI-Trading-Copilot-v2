"""
Database Manager

Centralized SQLite database manager for the
AI Trading Copilot.

Responsibilities
----------------
✓ Database Connection Management
✓ Execute Queries
✓ Fetch Records
✓ Transactions
✓ Table Management
✓ Backup Support
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path
from typing import Any


class DatabaseManager:

    def __init__(
        self,
        database_path: str = "database/trades.db",
    ):

        self.database_path = Path(database_path)

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.connection = sqlite3.connect(
            self.database_path,
            check_same_thread=False,
        )

        self.connection.row_factory = sqlite3.Row

    # --------------------------------------------------

    @property
    def cursor(self):

        return self.connection.cursor()

    # --------------------------------------------------

    def execute(
        self,
        query: str,
        parameters: tuple = (),
    ):

        cur = self.cursor

        cur.execute(
            query,
            parameters,
        )

        self.connection.commit()

        return cur

    # --------------------------------------------------

    def executemany(
        self,
        query: str,
        parameters: list[tuple],
    ):

        cur = self.cursor

        cur.executemany(
            query,
            parameters,
        )

        self.connection.commit()

        return cur

    # --------------------------------------------------

    def fetch_one(
        self,
        query: str,
        parameters: tuple = (),
    ) -> dict[str, Any] | None:

        row = self.execute(
            query,
            parameters,
        ).fetchone()

        if row is None:

            return None

        return dict(row)

    # --------------------------------------------------

    def fetch_all(
        self,
        query: str,
        parameters: tuple = (),
    ) -> list[dict[str, Any]]:

        rows = self.execute(
            query,
            parameters,
        ).fetchall()

        return [

            dict(row)

            for row in rows

        ]

    # --------------------------------------------------

    def begin(self):

        self.connection.execute(
            "BEGIN"
        )

    # --------------------------------------------------

    def commit(self):

        self.connection.commit()

    # --------------------------------------------------

    def rollback(self):

        self.connection.rollback()

    # --------------------------------------------------

    def create_table(
        self,
        sql: str,
    ):

        self.execute(sql)

    # --------------------------------------------------

    def table_exists(
        self,
        table_name: str,
    ) -> bool:

        result = self.fetch_one(

            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            AND name=?
            """,

            (table_name,),

        )

        return result is not None

    # --------------------------------------------------

    def list_tables(
        self,
    ) -> list[str]:

        rows = self.fetch_all(

            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            ORDER BY name
            """

        )

        return [

            row["name"]

            for row in rows

        ]

    # --------------------------------------------------

    def backup(
        self,
        destination: str,
    ):

        self.connection.commit()

        destination = Path(destination)

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(

            self.database_path,

            destination,

        )

    # --------------------------------------------------

    def vacuum(self):

        self.connection.execute(
            "VACUUM"
        )

    # --------------------------------------------------

    def close(self):

        self.connection.close()

    # --------------------------------------------------

    def summary(self):

        return {

            "database": str(

                self.database_path

            ),

            "tables": self.list_tables(),

            "table_count": len(

                self.list_tables()

            ),

            "connected": self.connection is not None,

        }