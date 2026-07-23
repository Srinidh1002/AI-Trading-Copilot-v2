"""
Testing Dashboard

Unified testing dashboard for the AI Trading Copilot.

Responsibilities
----------------
✓ System Health
✓ Unit Tests
✓ Integration Tests
✓ Regression Tests
✓ Performance Tests
✓ Stress Tests
✓ Scenario Tests
✓ Benchmark Results
✓ Overall Status
✓ Streamlit Ready
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from services.testing.benchmark_runner import BenchmarkRunner
from services.testing.regression_test import RegressionTest
from services.testing.scenario_runner import ScenarioRunner
from services.testing.stress_test import StressTest
from services.testing.system_health import SystemHealth
from services.testing.test_runner import TestRunner


class TestDashboard:

    def __init__(self):

        self.dashboard: dict[str, Any] = {}

    # --------------------------------------------------

    def load_health(self):

        health = SystemHealth()

        self.dashboard["health"] = health.overall()

    # --------------------------------------------------

    def load_tests(self):

        runner = TestRunner()

        self.dashboard["tests"] = runner.run_all()

    # --------------------------------------------------

    def load_regression(self):

        regression = RegressionTest()

        self.dashboard["regression"] = regression.run()

    # --------------------------------------------------

    def load_stress(self):

        stress = StressTest()

        self.dashboard["stress"] = stress.run()

    # --------------------------------------------------

    def load_scenarios(self):

        scenarios = ScenarioRunner()

        self.dashboard["scenarios"] = scenarios.run_all()

    # --------------------------------------------------

    def load_benchmarks(self):

        benchmark = BenchmarkRunner()

        self.dashboard["benchmarks"] = benchmark.run()

    # --------------------------------------------------

    def refresh(self):

        self.dashboard.clear()

        self.load_health()

        self.load_tests()

        self.load_regression()

        self.load_stress()

        self.load_scenarios()

        self.load_benchmarks()

        return self.summary()

    # --------------------------------------------------

    def overall_status(self) -> bool:

        if not self.dashboard:

            self.refresh()

        checks = []

        health = self.dashboard.get("health", {})

        checks.append(

            health.get(

                "health_score",

                0,

            ) >= 80

        )

        tests = self.dashboard.get("tests", {})

        checks.append(

            tests.get(

                "overall_success",

                False,

            )

        )

        regression = self.dashboard.get(

            "regression",

            {},

        )

        checks.append(

            regression.get(

                "success",

                False,

            )

        )

        stress = self.dashboard.get(

            "stress",

            {},

        )

        checks.append(

            stress.get(

                "stable",

                False,

            )

        )

        benchmark = self.dashboard.get(

            "benchmarks",

            {},

        )

        checks.append(

            benchmark.get(

                "overall_score",

                0,

            ) >= 80

        )

        return all(checks)

    # --------------------------------------------------

    def health_score(self):

        if not self.dashboard:

            self.refresh()

        return self.dashboard.get(

            "health",

            {},

        ).get(

            "health_score",

            0,

        )

    # --------------------------------------------------

    def total_tests(self):

        if not self.dashboard:

            self.refresh()

        return self.dashboard.get(

            "tests",

            {},

        ).get(

            "total_tests",

            0,

        )

    # --------------------------------------------------

    def passed_tests(self):

        if not self.dashboard:

            self.refresh()

        return self.dashboard.get(

            "tests",

            {},

        ).get(

            "passed",

            0,

        )

    # --------------------------------------------------

    def failed_tests(self):

        if not self.dashboard:

            self.refresh()

        return self.dashboard.get(

            "tests",

            {},

        ).get(

            "failed",

            0,

        )

    # --------------------------------------------------

    def benchmark_score(self):

        if not self.dashboard:

            self.refresh()

        return self.dashboard.get(

            "benchmarks",

            {},

        ).get(

            "overall_score",

            0,

        )

    # --------------------------------------------------

    def scenario_summary(self):

        if not self.dashboard:

            self.refresh()

        return self.dashboard.get(

            "scenarios",

            {},

        )

    # --------------------------------------------------

    def streamlit_data(self):

        if not self.dashboard:

            self.refresh()

        return {

            "overall_status": self.overall_status(),

            "health_score": self.health_score(),

            "benchmark_score": self.benchmark_score(),

            "total_tests": self.total_tests(),

            "passed": self.passed_tests(),

            "failed": self.failed_tests(),

            "scenario_summary": self.scenario_summary(),

            "generated_at": datetime.now().isoformat(),

        }

    # --------------------------------------------------

    def summary(self):

        return {

            "timestamp": datetime.now().isoformat(),

            "overall_status": self.overall_status(),

            "health_score": self.health_score(),

            "benchmark_score": self.benchmark_score(),

            "total_tests": self.total_tests(),

            "passed_tests": self.passed_tests(),

            "failed_tests": self.failed_tests(),

            "dashboard": self.dashboard,

        }


# ------------------------------------------------------
# Standalone Execution
# ------------------------------------------------------

if __name__ == "__main__":

    dashboard = TestDashboard()

    report = dashboard.refresh()

    print("\n" + "=" * 70)
    print(" AI TRADING COPILOT - TEST DASHBOARD")
    print("=" * 70)
    print(f"Overall Status : {report['overall_status']}")
    print(f"Health Score   : {report['health_score']}%")
    print(f"Benchmark      : {report['benchmark_score']}%")
    print(f"Total Tests    : {report['total_tests']}")
    print(f"Passed         : {report['passed_tests']}")
    print(f"Failed         : {report['failed_tests']}")
    print("=" * 70)