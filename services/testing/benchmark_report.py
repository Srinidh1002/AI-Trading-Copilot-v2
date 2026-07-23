"""
Benchmark Report

Generates benchmark reports from the BenchmarkRunner.

Responsibilities
----------------
✓ JSON Benchmark Report
✓ Text Benchmark Report
✓ Performance Summary
✓ Memory Summary
✓ Benchmark Statistics
✓ Timestamped Export
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from services.testing.benchmark_runner import BenchmarkRunner


class BenchmarkReport:

    def __init__(
        self,
        output_directory: str = "reports/benchmarks",
    ):

        self.output_directory = Path(output_directory)

        self.output_directory.mkdir(

            parents=True,

            exist_ok=True,

        )

        self.runner = BenchmarkRunner()

        self.report: dict[str, Any] = {}

    # --------------------------------------------------

    def run(self):

        self.report = self.runner.run()

        return self.report

    # --------------------------------------------------

    def statistics(self):

        if not self.report:

            self.run()

        results = self.report["results"]

        benchmark_count = len(results)

        passed = sum(

            1

            for benchmark in results.values()

            if benchmark["passed"]

        )

        failed = benchmark_count - passed

        average_time = round(

            sum(

                benchmark["average_time_ms"]

                for benchmark in results.values()

            )

            / benchmark_count,

            3,

        ) if benchmark_count else 0

        peak_memory = round(

            max(

                benchmark["memory_kb"]

                for benchmark in results.values()

            ),

            2,

        ) if benchmark_count else 0

        return {

            "overall_score": self.report.get(

                "overall_score",

                0,

            ),

            "benchmarks": benchmark_count,

            "passed": passed,

            "failed": failed,

            "average_time_ms": average_time,

            "peak_memory_kb": peak_memory,

            "fastest": self.report.get(

                "fastest",

            ),

            "slowest": self.report.get(

                "slowest",

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

            "AI TRADING COPILOT BENCHMARK REPORT",

            "=" * 70,

            f"Generated        : {datetime.now().isoformat()}",

            "",

            f"Overall Score    : {stats['overall_score']}%",

            f"Benchmarks       : {stats['benchmarks']}",

            f"Passed           : {stats['passed']}",

            f"Failed           : {stats['failed']}",

            f"Average Time     : {stats['average_time_ms']} ms",

            f"Peak Memory      : {stats['peak_memory_kb']} KB",

            f"Fastest          : {stats['fastest']}",

            f"Slowest          : {stats['slowest']}",

            "",

            "=" * 70,

            "BENCHMARK DETAILS",

            "=" * 70,

        ]

        for name, result in self.report["results"].items():

            lines.extend([

                "",

                f"Benchmark        : {name}",

                f"Passed           : {result['passed']}",

                f"Iterations       : {result['iterations']}",

                f"Average Time     : {result['average_time_ms']} ms",

                f"Minimum Time     : {result['minimum_time_ms']} ms",

                f"Maximum Time     : {result['maximum_time_ms']} ms",

                f"Peak Memory      : {result['memory_kb']} KB",

            ])

            if result["error"]:

                lines.append(

                    f"Error            : {result['error']}"

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

            / f"benchmark_report_{datetime.now():%Y%m%d_%H%M%S}.json"

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

                default=str,

            )

        return filename

    # --------------------------------------------------

    def save_text(self):

        filename = (

            self.output_directory

            / f"benchmark_report_{datetime.now():%Y%m%d_%H%M%S}.txt"

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

    report = BenchmarkReport()

    report.run()

    files = report.export()

    print("\nBenchmark reports generated successfully.\n")

    print(f"JSON : {files['json']}")

    print(f"TEXT : {files['text']}")