"""
User Database

Persistent storage for application users.

Responsibilities
----------------
✓ Create User Table
✓ Register Users
✓ Update User Details
✓ Delete Users
✓ Fetch Users
✓ Authentication Support
✓ Role Management
✓ User Statistics
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from services.database.database_manager import DatabaseManager


class UserDatabase:

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
            CREATE TABLE IF NOT EXISTS users (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                username TEXT UNIQUE NOT NULL,

                email TEXT UNIQUE,

                password_hash TEXT NOT NULL,

                full_name TEXT,

                role TEXT NOT NULL,

                active INTEGER DEFAULT 1,

                created_at TEXT,

                last_login TEXT

            )
            """
        )

    # --------------------------------------------------

    def create_user(
        self,
        username: str,
        password_hash: str,
        role: str = "VIEWER",
        email: str | None = None,
        full_name: str | None = None,
    ) -> int:

        cursor = self.db.execute(
            """
            INSERT INTO users (

                username,
                email,
                password_hash,
                full_name,
                role,
                active,
                created_at,
                last_login

            )

            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                username,
                email,
                password_hash,
                full_name,
                role,
                1,
                datetime.now().isoformat(),
                None,
            ),
        )

        return cursor.lastrowid

    # --------------------------------------------------

    def update_user(
        self,
        user_id: int,
        **fields: Any,
    ):

        if not fields:
            return

        columns = ", ".join(
            f"{key}=?"
            for key in fields
        )

        values = list(fields.values())
        values.append(user_id)

        self.db.execute(
            f"""
            UPDATE users

            SET {columns}

            WHERE id=?
            """,
            tuple(values),
        )

    # --------------------------------------------------

    def update_last_login(
        self,
        username: str,
    ):

        self.db.execute(
            """
            UPDATE users

            SET last_login=?

            WHERE username=?
            """,
            (
                datetime.now().isoformat(),
                username,
            ),
        )

    # --------------------------------------------------

    def delete_user(
        self,
        user_id: int,
    ):

        self.db.execute(
            """
            DELETE FROM users

            WHERE id=?
            """,
            (user_id,),
        )

    # --------------------------------------------------

    def get_user(
        self,
        user_id: int,
    ) -> dict[str, Any] | None:

        return self.db.fetch_one(
            """
            SELECT *

            FROM users

            WHERE id=?
            """,
            (user_id,),
        )

    # --------------------------------------------------

    def get_user_by_username(
        self,
        username: str,
    ) -> dict[str, Any] | None:

        return self.db.fetch_one(
            """
            SELECT *

            FROM users

            WHERE username=?
            """,
            (username,),
        )

    # --------------------------------------------------

    def get_user_by_email(
        self,
        email: str,
    ) -> dict[str, Any] | None:

        return self.db.fetch_one(
            """
            SELECT *

            FROM users

            WHERE email=?
            """,
            (email,),
        )

    # --------------------------------------------------

    def all_users(self):

        return self.db.fetch_all(
            """
            SELECT *

            FROM users

            ORDER BY username
            """
        )

    # --------------------------------------------------

    def active_users(self):

        return self.db.fetch_all(
            """
            SELECT *

            FROM users

            WHERE active=1

            ORDER BY username
            """
        )

    # --------------------------------------------------

    def deactivate_user(
        self,
        username: str,
    ):

        self.db.execute(
            """
            UPDATE users

            SET active=0

            WHERE username=?
            """,
            (username,),
        )

    # --------------------------------------------------

    def activate_user(
        self,
        username: str,
    ):

        self.db.execute(
            """
            UPDATE users

            SET active=1

            WHERE username=?
            """,
            (username,),
        )

    # --------------------------------------------------

    def change_role(
        self,
        username: str,
        role: str,
    ):

        self.db.execute(
            """
            UPDATE users

            SET role=?

            WHERE username=?
            """,
            (
                role,
                username,
            ),
        )

    # --------------------------------------------------

    def total_users(self) -> int:

        row = self.db.fetch_one(
            """
            SELECT COUNT(*) AS total

            FROM users
            """
        )

        return row["total"]

    # --------------------------------------------------

    def summary(self):

        return {

            "total_users": self.total_users(),

            "active_users": len(self.active_users()),

        }