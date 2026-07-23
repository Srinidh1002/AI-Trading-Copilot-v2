"""
Regression Test

Ensures that previously implemented functionality
continues to work correctly after new code changes.

Responsibilities
----------------
✓ Database Regression
✓ Cache Regression
✓ Configuration Regression
✓ File Manager Regression
✓ Validator Regression
✓ Helper Regression
✓ Overall Regression Report
"""

from __future__ import annotations

from typing import Any

from services.config.config_manager import ConfigManager
from services.database.database_manager import DatabaseManager
from services.utils.cache_manager import CacheManager
from services.utils.file_manager import FileManager
from services.utils.validators import Validators
from services.utils import helpers


class RegressionTest:

    def __init__(self):

        self.results: dict[str, dict[str, Any]] = {}

    # --------------------------------------------------

    def _run_test(
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

    def database_regression(self):

        db = DatabaseManager()

        row = db.fetch_one(

            "SELECT 1 AS value"

        )

        assert row["value"] == 1

        db.close()

    # --------------------------------------------------

    def cache_regression(self):

        cache = CacheManager()

        cache.set(

            "regression",

            100,

        )

        assert cache.get(

            "regression"

        ) == 100

        cache.delete(

            "regression"

        )

        assert cache.get(

            "regression"

        ) is None

    # --------------------------------------------------

    def config_regression(self):

        config = ConfigManager()

        config.set(

            "REGRESSION_TEST",

            "PASS",

        )

        assert (

            config.get(

                "REGRESSION_TEST"

            )

            == "PASS"

        )

    # --------------------------------------------------

    def file_manager_regression(self):

        filename = "regression_test.txt"

        FileManager.write_text(

            filename,

            "Regression OK",

        )

        text = FileManager.read_text(

            filename,

        )

        assert text == "Regression OK"

        FileManager.delete(

            filename,

        )

    # --------------------------------------------------

    def validator_regression(self):

        assert Validators.is_email(

            "user@test.com"

        )

        assert Validators.is_positive_number(

            123

        )

        assert Validators.is_symbol(

            "^NSEI"

        )

    # --------------------------------------------------

    def helper_regression(self):

        assert (

            helpers.round_number(

                25.6789,

                2,

            )

            == 25.68

        )

        assert (

            helpers.round_number(

                10,

                0,

            )

            == 10

        )

    # --------------------------------------------------

    def run(self):

        self.results.clear()

        self._run_test(

            "Database",

            self.database_regression,

        )

        self._run_test(

            "Cache",

            self.cache_regression,

        )

        self._run_test(

            "Configuration",

            self.config_regression,

        )

        self._run_test(

            "File Manager",

            self.file_manager_regression,

        )

        self._run_test(

            "Validators",

            self.validator_regression,

        )

        self._run_test(

            "Helpers",

            self.helper_regression,

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

    def success_rate(self):

        if not self.results:

            return 0.0

        return round(

            (self.passed() / len(self.results)) * 100,

            2,

        )

    # --------------------------------------------------

    def summary(self):

        return {

            "total_tests": len(

                self.results

            ),

            "passed": self.passed(),

            "failed": self.failed(),

            "success_rate": self.success_rate(),

            "success": self.failed() == 0,

            "results": self.results,

        }