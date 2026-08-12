import pytest

from services.reports.paper_certification_weekly_report import (
    build_paper_certification_weekly_report,
)
from tests.r79_reporting_helpers import (
    build_daily,
    clone_daily,
)


def test_weekly_report_aggregates_only_reconciled_daily_reports():
    first = build_daily()
    second = clone_daily(
        first,
        report_id="daily-2",
        day_offset=1,
    )

    report = build_paper_certification_weekly_report(
        report_id="weekly-1",
        week_started_on=first.session_date,
        week_ended_on=second.session_date,
        generated_at=second.generated_at,
        daily_reports=(second, first),
    )

    assert report.daily_report_ids == (
        "daily-1",
        "daily-2",
    )
    assert report.official_prediction_count == 2
    assert report.closed_position_count == 2
    assert report.net_pnl == first.net_pnl + second.net_pnl
    assert report.ending_capital == second.ending_capital
    assert {
        item.key
        for item in report.market_performance
    } == {"NIFTY"}
    assert {
        item.key
        for item in report.confidence_band_performance
    } == {"HIGH"}
    assert {
        item.key
        for item in report.regime_performance
    } == {"TRENDING"}
    assert {
        item.key
        for item in report.policy_version_performance
    } == {"1.0"}


def test_weekly_report_rejects_capital_discontinuity():
    first = build_daily()
    second = clone_daily(
        first,
        report_id="daily-2",
        day_offset=1,
    )
    from dataclasses import replace

    second = replace(
        second,
        starting_capital=second.starting_capital + 1.0,
        ending_capital=second.ending_capital + 1.0,
    )

    with pytest.raises(
        ValueError,
        match="capital continuity",
    ):
        build_paper_certification_weekly_report(
            report_id="weekly-1",
            week_started_on=first.session_date,
            week_ended_on=second.session_date,
            generated_at=second.generated_at,
            daily_reports=(first, second),
        )



