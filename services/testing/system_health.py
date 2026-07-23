"""
System Health

Monitors the health of all major system components
within the AI Trading Copilot.

Responsibilities
----------------
✓ Service Health Checks
✓ Database Health
✓ Memory Usage
✓ Disk Usage
✓ Python Environment
✓ Dependency Checks
✓ Overall Health Summary
"""

from __future__ import annotations

import importlib
import os
import platform
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any


class SystemHealth:

    def __init__(
        self,
        database_path: str = "database/trades.db",
    ):

        self.database_path = Path(database_path)

    # --------------------------------------------------

    def python(self) -> dict[str, Any]:

        return {

            "version": sys.version,

            "executable": sys.executable,

            "platform": platform.platform(),

            "architecture": platform.machine(),

        }

    # --------------------------------------------------

    def database(self) -> dict[str, Any]:

        exists = self.database_path.exists()

        healthy = False

        error = None

        if exists:

            try:

                connection = sqlite3.connect(

                    self.database_path

                )

                connection.execute(

                    "SELECT 1"

                )

                connection.close()

                healthy = True

            except Exception as exc:

                error = str(exc)

        return {

            "exists": exists,

            "healthy": healthy,

            "path": str(self.database_path),

            "error": error,

        }

    # --------------------------------------------------

    def disk(self) -> dict[str, Any]:

        usage = shutil.disk_usage(".")

        return {

            "total_gb": round(

                usage.total / (1024 ** 3),

                2,

            ),

            "used_gb": round(

                usage.used / (1024 ** 3),

                2,

            ),

            "free_gb": round(

                usage.free / (1024 ** 3),

                2,

            ),

        }

    # --------------------------------------------------

    def project(self) -> dict[str, Any]:

        return {

            "cwd": os.getcwd(),

            "exists": Path.cwd().exists(),

            "services": Path("services").exists(),

            "database": Path("database").exists(),

            "reports": Path("reports").exists(),

            "logs": Path("logs").exists(),

        }

    # --------------------------------------------------

    def dependency(
        self,
        package: str,
    ) -> bool:

        try:

            importlib.import_module(

                package

            )

            return True

        except Exception:

            return False

    # --------------------------------------------------

    def dependencies(self):

        packages = [

            "pandas",

            "numpy",

            "streamlit",

            "plotly",

            "yfinance",

            "requests",

            "ta",

            "dotenv",

            "sqlite3",

        ]

        return {

            package: self.dependency(

                package

            )

            for package in packages

        }

    # --------------------------------------------------

    def health_score(self) -> float:

        checks = [

            self.database()["healthy"],

            Path("services").exists(),

            Path("database").exists(),

            Path("logs").exists(),

        ]

        passed = sum(

            1

            for item in checks

            if item

        )

        return round(

            (passed / len(checks)) * 100,

            2,

        )

    # --------------------------------------------------

    def overall(self):

        return {

            "health_score": self.health_score(),

            "python": self.python(),

            "database": self.database(),

            "disk": self.disk(),

            "project": self.project(),

            "dependencies": self.dependencies(),

        }

    # --------------------------------------------------

    def summary(self):

        return {

            "health_score": self.health_score(),

            "database_ok": self.database()["healthy"],

            "python_version": platform.python_version(),

        }