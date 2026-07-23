"""
Log Database

Persistent storage for system and audit logs.

Responsibilities
----------------
✓ Create Log Table
✓ Insert Logs
✓ Query Logs
✓ Filter by Level
✓ Filter by Module
✓ Delete Old Logs
✓ Log Statistics
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from services.database.database_manager import DatabaseManager


class LogDatabase:

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
            CREATE TABLE IF NOT EXISTS logs (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                timestamp TEXT NOT NULL,

                level TEXT NOT NULL,

                module TEXT,

                message TEXT NOT NULL,

                details TEXT

            )
            """
        )

    # --------------------------------------------------

    def insert_log(
        self,
        level: str,
        module: str,
        message: str,
        details: str | None = None,
    ) -> int:

        cursor = self.db.execute(
            """
            INSERT INTO logs (

                timestamp,
                level,
                module,
                message,
                details

            )

            VALUES (?,?,?,?,?)
            """,
            (
                datetime.now().isoformat(),
                level.upper(),
                module,
                message,
                details,
            ),
        )

        return cursor.lastrowid

    # --------------------------------------------------

    def get_log(
        self,
        log_id: int,
    ) -> dict[str, Any] | None:

        return self.db.fetch_one(
            """
            SELECT *

            FROM logs

            WHERE id=?
            """,
            (log_id,),
        )

    # --------------------------------------------------

    def all_logs(self):

        return self.db.fetch_all(
            """
            SELECT *

            FROM logs

            ORDER BY id DESC
            """
        )

    # --------------------------------------------------

    def logs_by_level(
        self,
        level: str,
    ):

        return self.db.fetch_all(
            """
            SELECT *

            FROM logs

            WHERE level=?

            ORDER BY id DESC
            """,
            (
                level.upper(),
            ),
        )

    # --------------------------------------------------

    def logs_by_module(
        self,
        module: str,
    ):

        return self.db.fetch_all(
            """
            SELECT *

            FROM logs

            WHERE module=?

            ORDER BY id DESC
            """,
            (module,),
        )

    # --------------------------------------------------

    def latest_logs(
        self,
        limit: int = 100,
    ):

        return self.db.fetch_all(
            """
            SELECT *

            FROM logs

            ORDER BY id DESC

            LIMIT ?
            """,
            (limit,),
        )

    # --------------------------------------------------

    def search_logs(
        self,
        keyword: str,
    ):

        return self.db.fetch_all(
            """
            SELECT *

            FROM logs

            WHERE message LIKE ?

            ORDER BY id DESC
            """,
            (
                f"%{keyword}%",
            ),
        )

    # --------------------------------------------------

    def delete_log(
        self,
        log_id: int,
    ):

        self.db.execute(
            """
            DELETE FROM logs

            WHERE id=?
            """,
            (log_id,),
        )

    # --------------------------------------------------

    def clear_logs(self):

        self.db.execute(
            """
            DELETE FROM logs
            """
        )

    # --------------------------------------------------

    def delete_before(
        self,
        timestamp: str,
    ):

        self.db.execute(
            """
            DELETE FROM logs

            WHERE timestamp < ?
            """,
            (timestamp,),
        )

    # --------------------------------------------------

    def total_logs(self) -> int:

        row = self.db.fetch_one(
            """
            SELECT COUNT(*) AS total

            FROM logs
            """
        )

        return row["total"]

    # --------------------------------------------------

    def count_by_level(
        self,
        level: str,
    ) -> int:

        row = self.db.fetch_one(
            """
            SELECT COUNT(*) AS total

            FROM logs

            WHERE level=?
            """,
            (
                level.upper(),
            ),
        )

        return row["total"]

    # --------------------------------------------------

    def summary(self):

        return {

            "total_logs": self.total_logs(),

            "info_logs": self.count_by_level("INFO"),

            "warning_logs": self.count_by_level("WARNING"),

            "error_logs": self.count_by_level("ERROR"),

            "critical_logs": self.count_by_level("CRITICAL"),

        }