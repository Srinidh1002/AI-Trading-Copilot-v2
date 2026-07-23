"""
Scenario Report

Generates detailed reports for executed trading
scenarios.

Responsibilities
----------------
✓ JSON Report
✓ Text Report
✓ Win/Loss Statistics
✓ P&L Summary
✓ Scenario Distribution
✓ Timestamped Export
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from services.testing.scenario_runner import ScenarioRunner


class ScenarioReport:

    def __init__(self, output_directory: str = "reports/scenarios"):

        self.output_directory = Path(output_directory)

        self.output_directory.mkdir(

            parents=True,

            exist_ok=True,

        )

        self.runner = ScenarioRunner()

        self.report: dict[str, Any] = {}

    # --------------------------------------------------

    def run(self):

        self.report = self.runner.run_all()

        return self.report

    # --------------------------------------------------

    def statistics(self):

        if not self.report:

            self.run()

        results = self.report["results"]

        pnl_values = [

            item["estimated_pnl"]

            for item in results

        ]

        wins = [

            pnl

            for pnl in pnl_values

            if pnl > 0

        ]

        losses = [

            pnl

            for pnl in pnl_values

            if pnl <= 0

        ]

        scenario_counts = Counter(

            item["scenario"]

            for item in results

        )

        return {

            "total_scenarios": len(results),

            "wins": len(wins),

            "losses": len(losses),

            "win_rate": round(

                (len(wins) / len(results)) * 100,

                2,

            ) if results else 0,

            "net_pnl": round(

                sum(pnl_values),

                2,

            ),

            "average_pnl": round(

                sum(pnl_values) / len(results),

                2,

            ) if results else 0,

            "best_pnl": max(

                pnl_values,

                default=0,

            ),

            "worst_pnl": min(

                pnl_values,

                default=0,

            ),

            "scenario_distribution": dict(

                scenario_counts

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

            "AI TRADING COPILOT SCENARIO REPORT",

            "=" * 70,

            f"Generated        : {datetime.now().isoformat()}",

            "",

            f"Total Scenarios  : {stats['total_scenarios']}",

            f"Wins             : {stats['wins']}",

            f"Losses           : {stats['losses']}",

            f"Win Rate         : {stats['win_rate']}%",

            f"Net P&L          : {stats['net_pnl']}",

            f"Average P&L      : {stats['average_pnl']}",

            f"Best P&L         : {stats['best_pnl']}",

            f"Worst P&L        : {stats['worst_pnl']}",

            "",

            "=" * 70,

            "SCENARIO RESULTS",

            "=" * 70,

        ]

        for scenario in self.report["results"]:

            lines.extend([

                "",

                f"Scenario     : {scenario['scenario']}",

                f"Trend        : {scenario['trend']}",

                f"Entry Price  : {scenario['entry_price']}",

                f"Exit Price   : {scenario['exit_price']}",

                f"P&L          : {scenario['estimated_pnl']}",

                f"Volatility   : {scenario['volatility']}",

                f"Status       : {scenario['status']}",

            ])

        lines.append("")

        lines.append("=" * 70)

        return "\n".join(lines)

    # --------------------------------------------------

    def save_json(self):

        if not self.report:

            self.run()

        filename = (

            self.output_directory

            / f"scenario_report_{datetime.now():%Y%m%d_%H%M%S}.json"

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

            / f"scenario_report_{datetime.now():%Y%m%d_%H%M%S}.txt"

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

    report = ScenarioReport()

    report.run()

    files = report.export()

    print("\nScenario reports generated successfully.\n")

    print(f"JSON : {files['json']}")

    print(f"TEXT : {files['text']}")