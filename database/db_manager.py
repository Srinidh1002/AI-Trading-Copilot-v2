"""
Database Connection Manager
"""

import sqlite3
from contextlib import contextmanager


DB = "database/ai_trading.db"


class DatabaseManager:

    def connect(self):

        conn = sqlite3.connect(
            DB,
            check_same_thread=False,
        )

        conn.row_factory = sqlite3.Row

        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA temp_store=MEMORY;")

        return conn
    @contextmanager
    def session(self):

        conn = self.connect()

        try:

            yield conn

            conn.commit()

        except Exception:

            conn.rollback()

            raise

        finally:

            conn.close()

db_manager = DatabaseManager()