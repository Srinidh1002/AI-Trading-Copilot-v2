from services.reports.paper_certification_monthly_report import (
    build_paper_certification_monthly_report,
)
from services.reports.paper_certification_weekly_report import (
    build_paper_certification_weekly_report,
)
from tests.r79_reporting_helpers import (
    build_daily,
    clone_daily,
)


def test_monthly_report_reconciles_daily_weekly_and_capital_curve():
    first = build_daily()
    second = clone_daily(
        first,
        report_id="daily-2",
        day_offset=1,
    )
    weekly = build_paper_certification_weekly_report(
        report_id="weekly-1",
        week_started_on=first.session_date,
        week_ended_on=second.session_date,
        generated_at=second.generated_at,
        daily_reports=(first, second),
    )

    report = build_paper_certification_monthly_report(
        report_id="monthly-1",
        month_started_on=first.session_date,
        month_ended_on=second.session_date,
        generated_at=second.generated_at,
        daily_reports=(second, first),
        weekly_reports=(weekly,),
    )

    assert report.daily_report_ids == (
        "daily-1",
        "daily-2",
    )
    assert report.weekly_report_ids == ("weekly-1",)
    assert report.net_pnl == weekly.net_pnl
    assert report.starting_capital == first.starting_capital
    assert report.ending_capital == second.ending_capital
    assert len(report.capital_curve) == 2
    assert report.maximum_drawdown_amount > 0.0
    assert report.maximum_drawdown_percent > 0.0
    assert {
        item.confidence_band
        for item in report.confidence_calibration
    } == {"HIGH"}
    assert {
        item.key
        for item in report.regime_contribution
    } == {"TRENDING"}
    assert {
        item.key
        for item in report.engine_contribution
    } == {"OPTION_CHAIN", "TECHNICAL"}
    assert {
        item.key
        for item in report.pillar_contribution
    } == {"LIQUIDITY", "MOMENTUM"}
    assert report.unresolved_audit == ()
    assert report.excluded_record_audit == ()


