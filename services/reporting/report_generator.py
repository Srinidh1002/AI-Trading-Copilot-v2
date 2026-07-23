"""
Report Generator

Generates institutional-grade trading reports
from portfolio, journal and analytics data.

Responsibilities
----------------
✓ Daily Report
✓ Weekly Report
✓ Monthly Report
✓ Performance Report
✓ Portfolio Report
✓ Risk Report
✓ Dashboard Summary
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


class ReportGenerator:

    # --------------------------------------------------

    @staticmethod
    def portfolio_report(
        portfolio_summary: dict[str, Any],
    ) -> dict:

        return {

            "generated_at": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

            "type": "Portfolio",

            "data": portfolio_summary,

        }

    # --------------------------------------------------

    @staticmethod
    def performance_report(
        performance_summary: dict[str, Any],
    ) -> dict:

        return {

            "generated_at": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

            "type": "Performance",

            "data": performance_summary,

        }

    # --------------------------------------------------

    @staticmethod
    def trade_report(
        trade_summary: dict[str, Any],
    ) -> dict:

        return {

            "generated_at": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

            "type": "Trade Journal",

            "data": trade_summary,

        }

    # --------------------------------------------------

    @staticmethod
    def risk_report(
        risk_summary: dict[str, Any],
    ) -> dict:

        return {

            "generated_at": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

            "type": "Risk",

            "data": risk_summary,

        }

    # --------------------------------------------------

    @staticmethod
    def dashboard_report(

        portfolio: dict[str, Any],

        performance: dict[str, Any],

        journal: dict[str, Any],

        risk: dict[str, Any],

    ) -> dict:

        return {

            "generated_at": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

            "portfolio": portfolio,

            "performance": performance,

            "trade_journal": journal,

            "risk": risk,

        }

    # --------------------------------------------------

    @staticmethod
    def full_report(

        portfolio: dict[str, Any],

        performance: dict[str, Any],

        journal: dict[str, Any],

        risk: dict[str, Any],

    ) -> dict:

        return {

            "report_name": "Institutional Trading Report",

            "generated_at": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

            "portfolio": portfolio,

            "performance": performance,

            "trade_journal": journal,

            "risk": risk,

        }