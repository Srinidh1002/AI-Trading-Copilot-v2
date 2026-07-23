"""
Settings Database

Persistent storage for application settings.

Responsibilities
----------------
✓ Create Settings Table
✓ Save Settings
✓ Update Settings
✓ Delete Settings
✓ Load Settings
✓ Group Settings
✓ Settings Statistics
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from services.database.database_manager import DatabaseManager


class SettingsDatabase:

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
            CREATE TABLE IF NOT EXISTS settings (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                setting_key TEXT UNIQUE NOT NULL,

                setting_value TEXT,

                category TEXT,

                description TEXT,

                updated_at TEXT

            )
            """
        )

    # --------------------------------------------------

    def set_setting(
        self,
        key: str,
        value: Any,
        category: str = "GENERAL",
        description: str | None = None,
    ):

        existing = self.get_setting(key)

        if existing:

            self.db.execute(
                """
                UPDATE settings

                SET
                    setting_value=?,
                    category=?,
                    description=?,
                    updated_at=?

                WHERE setting_key=?
                """,
                (
                    str(value),
                    category,
                    description,
                    datetime.now().isoformat(),
                    key,
                ),
            )

        else:

            self.db.execute(
                """
                INSERT INTO settings (

                    setting_key,
                    setting_value,
                    category,
                    description,
                    updated_at

                )

                VALUES (?,?,?,?,?)
                """,
                (
                    key,
                    str(value),
                    category,
                    description,
                    datetime.now().isoformat(),
                ),
            )

    # --------------------------------------------------

    def get_setting(
        self,
        key: str,
    ) -> dict[str, Any] | None:

        return self.db.fetch_one(
            """
            SELECT *

            FROM settings

            WHERE setting_key=?
            """,
            (key,),
        )

    # --------------------------------------------------

    def value(
        self,
        key: str,
        default: Any = None,
    ) -> Any:

        setting = self.get_setting(key)

        if setting is None:

            return default

        return setting["setting_value"]

    # --------------------------------------------------

    def delete_setting(
        self,
        key: str,
    ):

        self.db.execute(
            """
            DELETE FROM settings

            WHERE setting_key=?
            """,
            (key,),
        )

    # --------------------------------------------------

    def all_settings(self):

        return self.db.fetch_all(
            """
            SELECT *

            FROM settings

            ORDER BY setting_key
            """
        )

    # --------------------------------------------------

    def settings_by_category(
        self,
        category: str,
    ):

        return self.db.fetch_all(
            """
            SELECT *

            FROM settings

            WHERE category=?

            ORDER BY setting_key
            """,
            (category,),
        )

    # --------------------------------------------------

    def categories(self):

        rows = self.db.fetch_all(
            """
            SELECT DISTINCT category

            FROM settings

            ORDER BY category
            """
        )

        return [

            row["category"]

            for row in rows

        ]

    # --------------------------------------------------

    def total_settings(self) -> int:

        row = self.db.fetch_one(
            """
            SELECT COUNT(*) AS total

            FROM settings
            """
        )

        return row["total"]

    # --------------------------------------------------

    def exists(
        self,
        key: str,
    ) -> bool:

        return self.get_setting(key) is not None

    # --------------------------------------------------

    def clear(self):

        self.db.execute(
            """
            DELETE FROM settings
            """
        )

    # --------------------------------------------------

    def summary(self):

        return {

            "total_settings": self.total_settings(),

            "categories": self.categories(),

        }