"""Projection from certification reports into one dashboard view."""
from __future__ import annotations

from collections import defaultdict

from services.contracts.paper_certification_reporting_v1 import (
    PaperCertificationDailyReportV1,
    PaperCertificationMonthlyReportV1,
    PaperCertificationWeeklyReportV1,
)
from services.dashboard_read_models.dashboard_certification_view_v1 import (
    DashboardCertificationMarketViewV1,
    DashboardCertificationViewV1,
)


def _market_views(
    daily: PaperCertificationDailyReportV1,
) -> tuple[DashboardCertificationMarketViewV1, ...]:
    grouped = defaultdict(list)
    for fact in daily.prediction_facts:
        grouped[fact.market].append(fact)

    result = []
    for market in sorted(grouped):
        facts = tuple(grouped[market])
        official = tuple(
            item
            for item in facts
            if item.officially_counted
        )
        resolved = tuple(
            item
            for item in official
            if item.success is not None
        )
        closed = tuple(
            item
            for item in official
            if item.closed_position
        )
        success_count = sum(
            item.success is True
            for item in resolved
        )
        failure_count = sum(
            item.success is False
            for item in resolved
        )
        result.append(
            DashboardCertificationMarketViewV1(
                market=market,
                prediction_count=len(facts),
                official_count=len(official),
                success_count=success_count,
                failure_count=failure_count,
                closed_trade_count=len(closed),
                gross_pnl=sum(
                    item.gross_pnl
                    for item in closed
                ),
                net_pnl=sum(
                    item.net_pnl
                    for item in closed
                ),
                reliability_percent=(
                    success_count
                    / len(resolved)
                    * 100.0
                    if resolved
                    else None
                ),
            )
        )
    return tuple(result)


def project_dashboard_certification_view(
    *,
    view_id: str,
    daily_report: PaperCertificationDailyReportV1,
    weekly_report: PaperCertificationWeeklyReportV1 | None = None,
    monthly_report: PaperCertificationMonthlyReportV1 | None = None,
) -> DashboardCertificationViewV1:
    """Project exact reconciled certification reports for display."""

    if type(daily_report) is not PaperCertificationDailyReportV1:
        raise TypeError("daily_report")
    if (
        weekly_report is not None
        and type(weekly_report) is not PaperCertificationWeeklyReportV1
    ):
        raise TypeError("weekly_report")
    if (
        monthly_report is not None
        and type(monthly_report) is not PaperCertificationMonthlyReportV1
    ):
        raise TypeError("monthly_report")

    if daily_report.report_status != "RECONCILED":
        raise ValueError("daily report must be reconciled")
    if weekly_report is not None:
        if weekly_report.report_status != "RECONCILED":
            raise ValueError("weekly report must be reconciled")
        if daily_report.report_id not in weekly_report.daily_report_ids:
            raise ValueError(
                "weekly report does not include daily report"
            )
    if monthly_report is not None:
        if monthly_report.report_status != "RECONCILED":
            raise ValueError("monthly report must be reconciled")
        if daily_report.report_id not in monthly_report.daily_report_ids:
            raise ValueError(
                "monthly report does not include daily report"
            )
        if (
            weekly_report is not None
            and weekly_report.report_id
            not in monthly_report.weekly_report_ids
        ):
            raise ValueError(
                "monthly report does not include weekly report"
            )

    source = monthly_report or weekly_report
    starting_capital = (
        source.starting_capital
        if source is not None
        else daily_report.starting_capital
    )
    ending_capital = (
        source.ending_capital
        if source is not None
        else daily_report.ending_capital
    )
    net_pnl = (
        source.net_pnl
        if source is not None
        else daily_report.net_pnl
    )
    maximum_drawdown_amount = (
        source.maximum_drawdown_amount
        if source is not None
        else 0.0
    )
    maximum_drawdown_percent = (
        source.maximum_drawdown_percent
        if source is not None
        else 0.0
    )
    expectancy = (
        weekly_report.expectancy
        if weekly_report is not None
        else (
            daily_report.net_pnl
            / daily_report.closed_position_count
            if daily_report.closed_position_count
            else None
        )
    )
    reliability = (
        monthly_report.reliability_percent
        if monthly_report is not None
        else (
            weekly_report.reliability_percent
            if weekly_report is not None
            else (
                (
                    sum(
                        item.success is True
                        for item in daily_report.prediction_facts
                        if item.officially_counted
                        and item.success is not None
                    )
                    / sum(
                        item.success is not None
                        for item in daily_report.prediction_facts
                        if item.officially_counted
                    )
                    * 100.0
                )
                if any(
                    item.officially_counted
                    and item.success is not None
                    for item in daily_report.prediction_facts
                )
                else None
            )
        )
    )

    return DashboardCertificationViewV1(
        view_id=view_id,
        generated_at=(
            monthly_report.generated_at
            if monthly_report is not None
            else (
                weekly_report.generated_at
                if weekly_report is not None
                else daily_report.generated_at
            )
        ),
        as_of_date=daily_report.session_date,
        daily_report_id=daily_report.report_id,
        weekly_report_id=(
            weekly_report.report_id
            if weekly_report is not None
            else None
        ),
        monthly_report_id=(
            monthly_report.report_id
            if monthly_report is not None
            else None
        ),
        starting_capital=starting_capital,
        ending_capital=ending_capital,
        net_pnl=net_pnl,
        official_prediction_count=(
            daily_report.official_prediction_count
        ),
        pending_prediction_count=(
            daily_report.pending_outcome_count
        ),
        excluded_prediction_count=(
            daily_report.excluded_prediction_count
        ),
        closed_trade_count=daily_report.closed_position_count,
        win_count=daily_report.win_count,
        loss_count=daily_report.loss_count,
        break_even_count=daily_report.break_even_count,
        no_trade_cycle_count=daily_report.no_trade_cycle_count,
        maximum_drawdown_amount=maximum_drawdown_amount,
        maximum_drawdown_percent=maximum_drawdown_percent,
        expectancy=expectancy,
        reliability_percent=reliability,
        incident_count=len(daily_report.incidents),
        unresolved_incident_count=sum(
            not item.resolved
            for item in daily_report.incidents
        ),
        duplicate_attempt_count=len(
            daily_report.duplicate_attempts
        ),
        market_views=_market_views(daily_report),
        action_distribution=daily_report.action_distribution,
        outcome_distribution=daily_report.outcome_distribution,
        reconciliation_distribution=(
            daily_report.reconciliation_distribution
        ),
        incident_distribution=daily_report.incident_distribution,
        duplicate_distribution=daily_report.duplicate_distribution,
        unresolved_prediction_ids=tuple(
            item.prediction_id
            for item in daily_report.unresolved_audit
        ),
        excluded_prediction_ids=tuple(
            item.prediction_id
            for item in daily_report.excluded_audit
        ),
    )
