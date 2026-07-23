"""
Unit Test

Unit tests for individual utility and service components
of the AI Trading Copilot.

Responsibilities
----------------
✓ Helper Function Tests
✓ Validator Tests
✓ Cache Tests
✓ Config Tests
✓ File Manager Tests
✓ Database Tests
✓ Summary Report
"""

from __future__ import annotations

from typing import Any

from services.config.config_manager import ConfigManager
from services.database.database_manager import DatabaseManager
from services.utils.cache_manager import CacheManager
from services.utils.file_manager import FileManager
from services.utils.validators import Validators
from services.utils import helpers


class UnitTest:

    def __init__(self):

        self.results: dict[str, dict[str, Any]] = {}

    # --------------------------------------------------

    def _test(
        self,
        name: str,
        function,
    ):

        try:

            function()

            self.results[name] = {

                "passed": True,

                "message": "Passed",

            }

        except Exception as exc:

            self.results[name] = {

                "passed": False,

                "message": str(exc),

            }

    # --------------------------------------------------

    def helper_tests(self):

        assert helpers.round_number(12.3456, 2) == 12.35

        assert helpers.round_number(10.0, 0) == 10

    # --------------------------------------------------

    def validator_tests(self):

        assert Validators.is_email("abc@test.com")

        assert Validators.is_positive_number(100)

        assert Validators.is_symbol("^NSEI")

    # --------------------------------------------------

    def cache_tests(self):

        cache = CacheManager()

        cache.set("x", 100)

        assert cache.get("x") == 100

        cache.delete("x")

        assert cache.get("x") is None

    # --------------------------------------------------

    def config_tests(self):

        config = ConfigManager()

        config.set("UNIT_TEST", "PASS")

        assert config.get("UNIT_TEST") == "PASS"

    # --------------------------------------------------

    def file_manager_tests(self):

        filename = "unit_test.txt"

        FileManager.write_text(

            filename,

            "Testing",

        )

        text = FileManager.read_text(

            filename,

        )

        assert text == "Testing"

        FileManager.delete(

            filename,

        )

    # --------------------------------------------------

    def database_tests(self):

        db = DatabaseManager()

        row = db.fetch_one(

            "SELECT 1 AS value"

        )

        assert row["value"] == 1

        db.close()

    # --------------------------------------------------

    def run(self):

        self.results.clear()

        self._test(

            "Helpers",

            self.helper_tests,

        )

        self._test(

            "Validators",

            self.validator_tests,

        )

        self._test(

            "Cache",

            self.cache_tests,

        )

        self._test(

            "Configuration",

            self.config_tests,

        )

        self._test(

            "File Manager",

            self.file_manager_tests,

        )

        self._test(

            "Database",

            self.database_tests,

        )

        return self.summary()

    # --------------------------------------------------

    def passed(self):

        return sum(

            result["passed"]

            for result in self.results.values()

        )

    # --------------------------------------------------

    def failed(self):

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