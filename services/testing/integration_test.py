"""
Integration Test

Runs integration tests across the major
AI Trading Copilot components.

Responsibilities
----------------
✓ Database Connectivity Test
✓ Configuration Test
✓ Cache Test
✓ File Manager Test
✓ Validator Test
✓ Helper Function Test
✓ Health Report
"""

from __future__ import annotations

from typing import Any

from services.config.config_manager import ConfigManager
from services.database.database_manager import DatabaseManager
from services.utils.cache_manager import CacheManager
from services.utils.file_manager import FileManager
from services.utils.validators import Validators
from services.utils import helpers


class IntegrationTest:

    def __init__(self):

        self.results: dict[str, dict[str, Any]] = {}

    # --------------------------------------------------

    def _record(
        self,
        name: str,
        success: bool,
        details: str = "",
    ):

        self.results[name] = {

            "passed": success,

            "details": details,

        }

    # --------------------------------------------------

    def test_database(self):

        try:

            db = DatabaseManager()

            db.execute("SELECT 1")

            db.close()

            self._record(

                "Database",

                True,

                "Connection successful",

            )

        except Exception as exc:

            self._record(

                "Database",

                False,

                str(exc),

            )

    # --------------------------------------------------

    def test_config(self):

        try:

            config = ConfigManager()

            config.set(

                "TEST_KEY",

                "OK",

            )

            success = (

                config.get("TEST_KEY")

                == "OK"

            )

            self._record(

                "Configuration",

                success,

                "Read/Write OK",

            )

        except Exception as exc:

            self._record(

                "Configuration",

                False,

                str(exc),

            )

    # --------------------------------------------------

    def test_cache(self):

        try:

            cache = CacheManager()

            cache.set(

                "sample",

                123,

            )

            success = (

                cache.get("sample")

                == 123

            )

            self._record(

                "Cache",

                success,

                "Cache working",

            )

        except Exception as exc:

            self._record(

                "Cache",

                False,

                str(exc),

            )

    # --------------------------------------------------

    def test_file_manager(self):

        try:

            filename = "integration_test.txt"

            FileManager.write_text(

                filename,

                "Hello",

            )

            text = FileManager.read_text(

                filename,

            )

            FileManager.delete(

                filename,

            )

            success = (

                text == "Hello"

            )

            self._record(

                "File Manager",

                success,

                "Read/Write/Delete OK",

            )

        except Exception as exc:

            self._record(

                "File Manager",

                False,

                str(exc),

            )

    # --------------------------------------------------

    def test_validators(self):

        try:

            success = (

                Validators.is_email(

                    "test@example.com"

                )

                and Validators.is_positive_number(

                    10

                )

                and Validators.is_symbol(

                    "^NSEI"

                )

            )

            self._record(

                "Validators",

                success,

                "Validation OK",

            )

        except Exception as exc:

            self._record(

                "Validators",

                False,

                str(exc),

            )

    # --------------------------------------------------

    def test_helpers(self):

        try:

            success = (

                helpers.round_number(

                    12.3456,

                    2,

                )

                == 12.35

            )

            self._record(

                "Helpers",

                success,

                "Helper functions OK",

            )

        except Exception as exc:

            self._record(

                "Helpers",

                False,

                str(exc),

            )

    # --------------------------------------------------

    def run(self):

        self.results.clear()

        self.test_database()

        self.test_config()

        self.test_cache()

        self.test_file_manager()

        self.test_validators()

        self.test_helpers()

        return self.summary()

    # --------------------------------------------------

    def passed(self) -> int:

        return sum(

            result["passed"]

            for result in self.results.values()

        )

    # --------------------------------------------------

    def failed(self) -> int:

        return len(

            self.results

        ) - self.passed()

    # --------------------------------------------------

    def summary(self):

        return {

            "total_tests": len(

                self.results

            ),

            "passed": self.passed(),

            "failed": self.failed(),

            "success": self.failed() == 0,

            "results": self.results,

        }