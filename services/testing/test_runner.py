"""
Test Runner

Centralized test runner for the AI Trading Copilot.

Responsibilities
----------------
✓ Run System Health Check
✓ Run Unit Tests
✓ Run Integration Tests
✓ Run Regression Tests
✓ Run Performance Tests
✓ Run Stress Tests
✓ Generate Consolidated Test Report
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from services.testing.system_health import SystemHealth
from services.testing.unit_test import UnitTest
from services.testing.integration_test import IntegrationTest
from services.testing.regression_test import RegressionTest
from services.testing.performance_test import PerformanceTest
from services.testing.stress_test import StressTest


class TestRunner:

    def __init__(self):

        self.results: dict[str, Any] = {}

    # --------------------------------------------------

    def run_health(self):

        health = SystemHealth()

        self.results["health"] = health.overall()

    # --------------------------------------------------

    def run_unit(self):

        tests = UnitTest()

        self.results["unit"] = tests.run()

    # --------------------------------------------------

    def run_integration(self):

        tests = IntegrationTest()

        self.results["integration"] = tests.run()

    # --------------------------------------------------

    def run_regression(self):

        tests = RegressionTest()

        self.results["regression"] = tests.run()

    # --------------------------------------------------

    def run_performance(self):

        tests = PerformanceTest()

        self.results["performance"] = tests.run()

    # --------------------------------------------------

    def run_stress(self):

        tests = StressTest()

        self.results["stress"] = tests.run()

    # --------------------------------------------------

    def run_all(self):

        self.results.clear()

        self.run_health()

        self.run_unit()

        self.run_integration()

        self.run_regression()

        self.run_performance()

        self.run_stress()

        return self.summary()

    # --------------------------------------------------

    def overall_status(self) -> bool:

        checks = []

        for key, value in self.results.items():

            if key == "health":

                checks.append(

                    value.get(

                        "health_score",

                        0,

                    ) >= 80

                )

            else:

                checks.append(

                    value.get(

                        "success",

                        False,

                    )

                )

        return all(checks)

    # --------------------------------------------------

    def total_tests(self) -> int:

        total = 0

        for key in [

            "unit",

            "integration",

            "regression",

            "stress",

        ]:

            if key in self.results:

                total += self.results[key].get(

                    "total_tests",

                    self.results[key].get(

                        "tests",

                        0,

                    ),

                )

        if "performance" in self.results:

            total += self.results["performance"].get(

                "benchmarks",

                0,

            )

        return total

    # --------------------------------------------------

    def passed_tests(self) -> int:

        total = 0

        for key in [

            "unit",

            "integration",

            "regression",

            "stress",

        ]:

            if key in self.results:

                total += self.results[key].get(

                    "passed",

                    0,

                )

        if "performance" in self.results:

            total += sum(

                1

                for benchmark in self.results["performance"][
                    "results"
                ].values()

                if benchmark["passed"]

            )

        return total

    # --------------------------------------------------

    def failed_tests(self) -> int:

        return self.total_tests() - self.passed_tests()

    # --------------------------------------------------

    def summary(self):

        return {

            "timestamp": datetime.now().isoformat(),

            "overall_success": self.overall_status(),

            "total_tests": self.total_tests(),

            "passed": self.passed_tests(),

            "failed": self.failed_tests(),

            "health_score": self.results.get(

                "health",

                {},

            ).get(

                "health_score",

                0,

            ),

            "results": self.results,

        }


# ------------------------------------------------------
# Standalone execution
# ------------------------------------------------------

if __name__ == "__main__":

    runner = TestRunner()

    report = runner.run_all()

    print("\n" + "=" * 70)
    print(" AI TRADING COPILOT - TEST REPORT")
    print("=" * 70)

    print(f"Overall Success : {report['overall_success']}")
    print(f"Health Score    : {report['health_score']}%")
    print(f"Total Tests     : {report['total_tests']}")
    print(f"Passed          : {report['passed']}")
    print(f"Failed          : {report['failed']}")

    print("=" * 70)