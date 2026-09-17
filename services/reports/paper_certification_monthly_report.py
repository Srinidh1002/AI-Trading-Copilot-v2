"""Monthly reconciliation of daily and weekly PAPER reports."""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import date, datetime

from services.contracts.paper_certification_reporting_v1 import (
    CertificationCapitalPointV1,
    CertificationConfidenceCalibrationV1,
    CertificationDrawdownPeriodV1,
    CertificationPerformanceSliceV1,
    CertificationPredictionFactV1,
    PaperCertificationDailyReportV1,
    PaperCertificationMonthlyReportV1,
    PaperCertificationWeeklyReportV1,
)


def _slice(
    key: str,
    facts: tuple[CertificationPredictionFactV1, ...],
) -> CertificationPerformanceSliceV1:
    resolved = tuple(
        item
        for item in facts
        if item.success is not None
    )
    closed = tuple(
        item
        for item in facts
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
    gross = sum(item.gross_pnl for item in closed)
    net = sum(item.net_pnl for item in closed)
    return CertificationPerformanceSliceV1(
        key=key,
        prediction_count=len(facts),
        resolved_count=len(resolved),
        success_count=success_count,
        failure_count=failure_count,
        closed_trade_count=len(closed),
        gross_pnl=gross,
        net_pnl=net,
        expectancy=(
            net / len(closed)
            if closed
            else None
        ),
        reliability_percent=(
            success_count / len(resolved) * 100.0
            if resolved
            else None
        ),
    )


def _group(
    facts: tuple[CertificationPredictionFactV1, ...],
    key,
) -> tuple[CertificationPerformanceSliceV1, ...]:
    grouped = defaultdict(list)
    for item in facts:
        grouped[key(item)].append(item)
    return tuple(
        _slice(group_key, tuple(grouped[group_key]))
        for group_key in sorted(grouped)
    )


def _calibration(
    facts: tuple[CertificationPredictionFactV1, ...],
) -> tuple[CertificationConfidenceCalibrationV1, ...]:
    grouped = defaultdict(list)
    for item in facts:
        if item.success is not None:
            grouped[item.confidence_band].append(item)
    result = []
    for band in sorted(grouped):
        values = tuple(grouped[band])
        average = statistics.fmean(
            item.confidence for item in values
        )
        observed = (
            sum(item.success is True for item in values)
            / len(values)
            * 100.0
        )
        result.append(
            CertificationConfidenceCalibrationV1(
                confidence_band=band,
                prediction_count=len(values),
                average_confidence_percent=average,
                observed_success_percent=observed,
                calibration_error_points=abs(
                    average - observed
                ),
            )
        )
    return tuple(result)


def _contribution_group(
    facts: tuple[CertificationPredictionFactV1, ...],
    attribute: str,
) -> tuple[CertificationPerformanceSliceV1, ...]:
    grouped = defaultdict(list)
    for item in facts:
        for key, _ in getattr(item, attribute):
            grouped[key].append(item)
    return tuple(
        _slice(key, tuple(grouped[key]))
        for key in sorted(grouped)
    )


def _drawdowns(
    curve: tuple[CertificationCapitalPointV1, ...],
) -> tuple[
    tuple[CertificationDrawdownPeriodV1, ...],
    float,
    float,
]:
    peak = curve[0].starting_capital
    peak_date = curve[0].session_date
    active_start = None
    trough_date = None
    trough_capital = None
    periods = []
    maximum_amount = 0.0
    maximum_percent = 0.0

    for point in curve:
        capital = point.ending_capital
        if capital >= peak:
            if active_start is not None:
                periods.append(
                    CertificationDrawdownPeriodV1(
                        started_on=active_start,
                        trough_on=trough_date,
                        recovered_on=point.session_date,
                        peak_capital=peak,
                        trough_capital=trough_capital,
                        drawdown_amount=peak - trough_capital,
                        drawdown_percent=(
                            (peak - trough_capital)
                            / peak
                            * 100.0
                        ),
                    )
                )
                active_start = None
                trough_date = None
                trough_capital = None
            peak = capital
            peak_date = point.session_date
            continue

        if active_start is None:
            active_start = peak_date
            trough_date = point.session_date
            trough_capital = capital
        elif capital < trough_capital:
            trough_date = point.session_date
            trough_capital = capital

        amount = peak - capital
        percent = amount / peak * 100.0
        maximum_amount = max(maximum_amount, amount)
        maximum_percent = max(maximum_percent, percent)

    if active_start is not None:
        periods.append(
            CertificationDrawdownPeriodV1(
                started_on=active_start,
                trough_on=trough_date,
                recovered_on=None,
                peak_capital=peak,
                trough_capital=trough_capital,
                drawdown_amount=peak - trough_capital,
                drawdown_percent=(
                    (peak - trough_capital)
                    / peak
                    * 100.0
                ),
            )
        )

    return tuple(periods), maximum_amount, maximum_percent


def _risk_adjusted(
    reports: tuple[PaperCertificationDailyReportV1, ...],
) -> float | None:
    returns = [
        item.net_pnl / item.starting_capital
        for item in reports
    ]
    if len(returns) < 2:
        return None
    deviation = statistics.pstdev(returns)
    if math.isclose(deviation, 0.0, abs_tol=1e-15):
        return None
    return (
        statistics.fmean(returns)
        / deviation
        * math.sqrt(len(returns))
    )


def build_paper_certification_monthly_report(
    *,
    report_id: str,
    month_started_on: date,
    month_ended_on: date,
    generated_at: datetime,
    daily_reports: tuple[
        PaperCertificationDailyReportV1, ...
    ],
    weekly_reports: tuple[
        PaperCertificationWeeklyReportV1, ...
    ],
) -> PaperCertificationMonthlyReportV1:
    """Reconcile monthly totals with every included daily and weekly report."""

    if type(daily_reports) is not tuple or any(
        type(item) is not PaperCertificationDailyReportV1
        for item in daily_reports
    ):
        raise TypeError("daily_reports")
    if type(weekly_reports) is not tuple or any(
        type(item) is not PaperCertificationWeeklyReportV1
        for item in weekly_reports
    ):
        raise TypeError("weekly_reports")
    if not daily_reports or not weekly_reports:
        raise ValueError("daily and weekly reports are required")
    if type(month_started_on) is not date:
        raise TypeError("month_started_on")
    if type(month_ended_on) is not date:
        raise TypeError("month_ended_on")
    if month_started_on > month_ended_on:
        raise ValueError("monthly date ordering")
    if (
        not isinstance(generated_at, datetime)
        or generated_at.tzinfo is None
        or generated_at.utcoffset() is None
    ):
        raise ValueError("generated_at")

    daily = tuple(
        sorted(
            daily_reports,
            key=lambda item: (
                item.session_date,
                item.report_id,
            ),
        )
    )
    weekly = tuple(
        sorted(
            weekly_reports,
            key=lambda item: (
                item.week_started_on,
                item.report_id,
            ),
        )
    )

    if len({item.report_id for item in daily}) != len(daily):
        raise ValueError("duplicate daily report_id")
    if len({item.session_date for item in daily}) != len(daily):
        raise ValueError("duplicate daily session_date")
    if len({item.report_id for item in weekly}) != len(weekly):
        raise ValueError("duplicate weekly report_id")
    if any(
        item.report_status != "RECONCILED"
        for item in (*daily, *weekly)
    ):
        raise ValueError("monthly input reports must be reconciled")
    if any(
        not (
            month_started_on
            <= item.session_date
            <= month_ended_on
        )
        for item in daily
    ):
        raise ValueError("daily report lies outside month")
    if any(
        item.week_started_on < month_started_on
        or item.week_ended_on > month_ended_on
        for item in weekly
    ):
        raise ValueError("weekly report lies outside month")

    for previous, current in zip(daily, daily[1:]):
        if not math.isclose(
            previous.ending_capital,
            current.starting_capital,
            abs_tol=1e-9,
        ):
            raise ValueError("daily capital continuity mismatch")

    daily_ids = tuple(item.report_id for item in daily)
    referenced_ids = tuple(
        report_id
        for item in weekly
        for report_id in item.daily_report_ids
    )
    if (
        len(set(referenced_ids)) != len(referenced_ids)
        or set(referenced_ids) != set(daily_ids)
    ):
        raise ValueError(
            "weekly reports must cover every daily report exactly once"
        )

    daily_by_id = {
        item.report_id: item
        for item in daily
    }
    for weekly_report in weekly:
        expected = tuple(
            item.report_id
            for item in daily
            if item.report_id
            in set(weekly_report.daily_report_ids)
        )
        if expected != weekly_report.daily_report_ids:
            raise ValueError(
                "weekly daily-report ordering mismatch"
            )
        expected_net = sum(
            daily_by_id[item_id].net_pnl
            for item_id in weekly_report.daily_report_ids
        )
        if not math.isclose(
            expected_net,
            weekly_report.net_pnl,
            abs_tol=1e-9,
        ):
            raise ValueError("weekly net P&L mismatch")

    daily_net = sum(item.net_pnl for item in daily)
    weekly_net = sum(item.net_pnl for item in weekly)
    if not math.isclose(daily_net, weekly_net, abs_tol=1e-9):
        raise ValueError(
            "monthly daily/weekly P&L reconciliation"
        )

    curve = tuple(
        CertificationCapitalPointV1(
            session_date=item.session_date,
            starting_capital=item.starting_capital,
            ending_capital=item.ending_capital,
            net_pnl=item.net_pnl,
        )
        for item in daily
    )
    drawdowns, max_amount, max_percent = _drawdowns(curve)

    facts = tuple(
        fact
        for report in daily
        for fact in report.prediction_facts
        if fact.officially_counted
    )
    resolved = tuple(
        item
        for item in facts
        if item.success is not None
    )
    success_count = sum(
        item.success is True
        for item in resolved
    )

    unresolved = tuple(
        item
        for report in daily
        for item in report.unresolved_audit
    )
    excluded = tuple(
        item
        for report in daily
        for item in report.excluded_audit
    )
    if len(
        {item.prediction_id for item in unresolved}
    ) != len(unresolved):
        raise ValueError("duplicate unresolved audit prediction")
    if len(
        {item.prediction_id for item in excluded}
    ) != len(excluded):
        raise ValueError("duplicate excluded audit prediction")

    return PaperCertificationMonthlyReportV1(
        report_id=report_id,
        month_started_on=month_started_on,
        month_ended_on=month_ended_on,
        generated_at=generated_at,
        daily_report_ids=daily_ids,
        weekly_report_ids=tuple(
            item.report_id
            for item in weekly
        ),
        starting_capital=daily[0].starting_capital,
        ending_capital=daily[-1].ending_capital,
        net_pnl=daily_net,
        capital_curve=curve,
        drawdown_periods=drawdowns,
        maximum_drawdown_amount=max_amount,
        maximum_drawdown_percent=max_percent,
        risk_adjusted_performance=_risk_adjusted(daily),
        reliability_percent=(
            success_count / len(resolved) * 100.0
            if resolved
            else None
        ),
        confidence_calibration=_calibration(facts),
        regime_contribution=_group(
            facts,
            lambda item: item.regime,
        ),
        engine_contribution=_contribution_group(
            facts,
            "engine_contributions",
        ),
        pillar_contribution=_contribution_group(
            facts,
            "pillar_contributions",
        ),
        policy_version_comparison=_group(
            facts,
            lambda item: item.policy_version,
        ),
        unresolved_audit=unresolved,
        excluded_record_audit=excluded,
    )
