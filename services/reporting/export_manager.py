"""
Export Manager

Exports institutional-grade trading reports
to JSON and CSV formats.

Responsibilities
----------------
✓ Export Portfolio Reports
✓ Export Performance Reports
✓ Export Trade Journal
✓ Export Dashboard Reports
✓ Export Full Reports
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


class ExportManager:

    # --------------------------------------------------

    @staticmethod
    def export_json(
        data: dict[str, Any],
        filepath: str,
    ) -> str:

        path = Path(filepath)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with open(
            path,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(

                data,

                file,

                indent=4,

                default=str,

            )

        return str(path)

    # --------------------------------------------------

    @staticmethod
    def export_csv(
        rows: list[dict[str, Any]],
        filepath: str,
    ) -> str:

        path = Path(filepath)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not rows:

            with open(
                path,
                "w",
                newline="",
                encoding="utf-8",
            ):
                pass

            return str(path)

        fieldnames = list(rows[0].keys())

        with open(

            path,

            "w",

            newline="",

            encoding="utf-8",

        ) as file:

            writer = csv.DictWriter(

                file,

                fieldnames=fieldnames,

            )

            writer.writeheader()

            writer.writerows(rows)

        return str(path)

    # --------------------------------------------------

    @staticmethod
    def export_trade_journal(
        trades: list[dict[str, Any]],
        filepath: str,
    ) -> str:

        return ExportManager.export_csv(

            trades,

            filepath,

        )

    # --------------------------------------------------

    @staticmethod
    def export_portfolio(
        portfolio: dict[str, Any],
        filepath: str,
    ) -> str:

        return ExportManager.export_json(

            portfolio,

            filepath,

        )

    # --------------------------------------------------

    @staticmethod
    def export_performance(
        performance: dict[str, Any],
        filepath: str,
    ) -> str:

        return ExportManager.export_json(

            performance,

            filepath,

        )

    # --------------------------------------------------

    @staticmethod
    def export_dashboard(
        dashboard: dict[str, Any],
        filepath: str,
    ) -> str:

        return ExportManager.export_json(

            dashboard,

            filepath,

        )

    # --------------------------------------------------

    @staticmethod
    def export_full_report(
        report: dict[str, Any],
        filepath: str,
    ) -> str:

        return ExportManager.export_json(

            report,

            filepath,

        )