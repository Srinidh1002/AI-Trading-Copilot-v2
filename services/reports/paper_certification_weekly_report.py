"""Weekly aggregation of valid daily PAPER certification reports."""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime

from services.contracts.paper_certification_reporting_v1 import (
    CertificationPerformanceSliceV1,
    CertificationPredictionFactV1,
    PaperCertificationDailyReportV1,
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


def _maximum_drawdown(
    reports: tuple[PaperCertificationDailyReportV1, ...],
) -> tuple[float, float]:
    peak = reports[0].starting_capital
    maximum_amount = 0.0
    maximum_percent = 0.0
    for report in reports:
        peak = max(peak, report.ending_capital)
        amount = peak - report.ending_capital
        percent = (
            amount / peak * 100.0
            if peak
            else 0.0
        )
        maximum_amount = max(maximum_amount, amount)
        maximum_percent = max(
            maximum_percent,
            percent,
        )
    return maximum_amount, maximum_percent


def build_paper_certification_weekly_report(
    *,
    report_id: str,
    week_started_on: date,
    week_ended_on: date,
    generated_at: datetime,
    daily_reports: tuple[
        PaperCertificationDailyReportV1, ...
    ],
) -> PaperCertificationWeeklyReportV1:
    """Aggregate only reconciled daily certification reports."""

    if type(daily_reports) is not tuple or any(
        type(item) is not PaperCertificationDailyReportV1
        for item in daily_reports
    ):
        raise TypeError("daily_reports")
    if not daily_reports:
        raise ValueError("daily_reports")
    if type(week_started_on) is not date:
        raise TypeError("week_started_on")
    if type(week_ended_on) is not date:
        raise TypeError("week_ended_on")
    if week_started_on > week_ended_on:
        raise ValueError("weekly date ordering")
    if (
        not isinstance(generated_at, datetime)
        or generated_at.tzinfo is None
        or generated_at.utcoffset() is None
    ):
        raise ValueError("generated_at")

    ordered = tuple(
        sorted(
            daily_reports,
            key=lambda item: (
                item.session_date,
                item.report_id,
            ),
        )
    )
    if len({item.report_id for item in ordered}) != len(ordered):
        raise ValueError("duplicate daily report_id")
    if len({item.session_date for item in ordered}) != len(ordered):
        raise ValueError("duplicate daily session_date")
    if any(
        item.report_status != "RECONCILED"
        for item in ordered
    ):
        raise ValueError(
            "weekly report requires reconciled daily reports"
        )
    if any(
        not (
            week_started_on
            <= item.session_date
            <= week_ended_on
        )
        for item in ordered
    ):
        raise ValueError(
            "daily report lies outside weekly period"
        )

    for previous, current in zip(ordered, ordered[1:]):
        if not math.isclose(
            previous.ending_capital,
            current.starting_capital,
            abs_tol=1e-9,
        ):
            raise ValueError(
                "daily capital continuity mismatch"
            )

    facts = tuple(
        fact
        for report in ordered
        for fact in report.prediction_facts
        if fact.officially_counted
    )
    closed = tuple(
        item
        for item in facts
        if item.closed_position
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
    net = sum(item.net_pnl for item in closed)
    daily_net = sum(item.net_pnl for item in ordered)
    if not math.isclose(net, daily_net, abs_tol=1e-9):
        raise ValueError(
            "weekly fact P&L does not match daily reports"
        )

    drawdown_amount, drawdown_percent = _maximum_drawdown(
        ordered
    )
    rejected = tuple(
        item
        for item in facts
        if not item.parent_selected
    )

    return PaperCertificationWeeklyReportV1(
        report_id=report_id,
        week_started_on=week_started_on,
        week_ended_on=week_ended_on,
        generated_at=generated_at,
        daily_report_ids=tuple(
            item.report_id
            for item in ordered
        ),
        starting_capital=ordered[0].starting_capital,
        ending_capital=ordered[-1].ending_capital,
        net_pnl=net,
        maximum_drawdown_amount=drawdown_amount,
        maximum_drawdown_percent=drawdown_percent,
        official_prediction_count=len(facts),
        closed_position_count=len(closed),
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
        market_performance=_group(
            facts,
            lambda item: item.market,
        ),
        confidence_band_performance=_group(
            facts,
            lambda item: item.confidence_band,
        ),
        regime_performance=_group(
            facts,
            lambda item: item.regime,
        ),
        direction_performance=_group(
            facts,
            lambda item: item.direction,
        ),
        time_of_day_performance=_group(
            facts,
            lambda item: item.time_of_day,
        ),
        contract_quality_performance=_group(
            facts,
            lambda item: item.contract_quality,
        ),
        spread_quality_performance=_group(
            facts,
            lambda item: item.spread_quality,
        ),
        liquidity_quality_performance=_group(
            facts,
            lambda item: item.liquidity_quality,
        ),
        rejected_signal_performance=_group(
            rejected,
            lambda item: item.outcome,
        ),
        policy_version_performance=_group(
            facts,
            lambda item: item.policy_version,
        ),
    )
