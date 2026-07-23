"""
Test Report

Generates consolidated reports from the TestRunner
results.

Responsibilities
----------------
✓ Generate JSON Report
✓ Generate Text Report
✓ Save Reports
✓ Execution Statistics
✓ Pass/Fail Summary
✓ Health Summary
✓ Timestamped Report Export
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from services.testing.test_runner import TestRunner


class TestReport:

    def __init__(self, output_directory: str = "reports/tests"):

        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.runner = TestRunner()

        self.report: dict[str, Any] = {}

    # --------------------------------------------------

    def run(self):

        self.report = self.runner.run_all()

        return self.report

    # --------------------------------------------------

    def statistics(self):

        if not self.report:

            self.run()

        total = self.report.get("total_tests", 0)
        passed = self.report.get("passed", 0)
        failed = self.report.get("failed", 0)

        success_rate = 0.0

        if total:

            success_rate = round(
                (passed / total) * 100,
                2,
            )

        return {

            "total_tests": total,

            "passed": passed,

            "failed": failed,

            "success_rate": success_rate,

            "health_score": self.report.get(
                "health_score",
                0,
            ),

            "overall_success": self.report.get(
                "overall_success",
                False,
            ),

        }

    # --------------------------------------------------

    def json_report(self):

        if not self.report:

            self.run()

        return self.report

    # --------------------------------------------------

    def text_report(self):

        if not self.report:

            self.run()

        stats = self.statistics()

        lines = [

            "=" * 70,

            "AI TRADING COPILOT TEST REPORT",

            "=" * 70,

            f"Generated        : {datetime.now().isoformat()}",

            "",

            f"Overall Success  : {stats['overall_success']}",

            f"Health Score     : {stats['health_score']}%",

            f"Total Tests      : {stats['total_tests']}",

            f"Passed           : {stats['passed']}",

            f"Failed           : {stats['failed']}",

            f"Success Rate     : {stats['success_rate']}%",

            "",

            "=" * 70,

            "MODULE RESULTS",

            "=" * 70,

        ]

        for module, result in self.report["results"].items():

            lines.append("")
            lines.append(module.upper())

            if isinstance(result, dict):

                for key, value in result.items():

                    if key == "results":

                        continue

                    lines.append(
                        f"{key:<20}: {value}"
                    )

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)

    # --------------------------------------------------

    def save_json(self):

        if not self.report:

            self.run()

        filename = (

            self.output_directory

            / f"test_report_{datetime.now():%Y%m%d_%H%M%S}.json"

        )

        with open(

            filename,

            "w",

            encoding="utf-8",

        ) as file:

            json.dump(

                self.report,

                file,

                indent=4,

            )

        return filename

    # --------------------------------------------------

    def save_text(self):

        filename = (

            self.output_directory

            / f"test_report_{datetime.now():%Y%m%d_%H%M%S}.txt"

        )

        with open(

            filename,

            "w",

            encoding="utf-8",

        ) as file:

            file.write(

                self.text_report()

            )

        return filename

    # --------------------------------------------------

    def export(self):

        json_file = self.save_json()

        text_file = self.save_text()

        return {

            "json": str(json_file),

            "text": str(text_file),

        }

    # --------------------------------------------------

    def summary(self):

        return self.statistics()


# ------------------------------------------------------
# Standalone Execution
# ------------------------------------------------------

if __name__ == "__main__":

    report = TestReport()

    report.run()

    files = report.export()

    print("\nTest reports generated successfully.\n")

    print(f"JSON : {files['json']}")
    print(f"TEXT : {files['text']}")