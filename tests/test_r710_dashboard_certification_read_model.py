from dataclasses import FrozenInstanceError

import pytest

from services.dashboard_read_models.dashboard_certification_projection import (
    project_dashboard_certification_view,
)
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


def reports():
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
    monthly = build_paper_certification_monthly_report(
        report_id="monthly-1",
        month_started_on=first.session_date,
        month_ended_on=second.session_date,
        generated_at=second.generated_at,
        daily_reports=(first, second),
        weekly_reports=(weekly,),
    )
    return first, second, weekly, monthly


def test_projection_is_immutable_deterministic_and_paper_only():
    _, daily, weekly, monthly = reports()

    first = project_dashboard_certification_view(
        view_id="certification-view-1",
        daily_report=daily,
        weekly_report=weekly,
        monthly_report=monthly,
    )
    second = project_dashboard_certification_view(
        view_id="certification-view-1",
        daily_report=daily,
        weekly_report=weekly,
        monthly_report=monthly,
    )

    assert first == second
    assert first.to_json() == second.to_json()
    assert len(first.semantic_hash) == 64
    assert first.execution_mode == "PAPER"
    assert first.live_execution_eligible is False
    assert first.broker_order_submission is False
    assert first.read_only is True

    with pytest.raises(FrozenInstanceError):
        first.net_pnl = 0.0


def test_projection_exposes_certification_dashboard_metrics():
    _, daily, weekly, monthly = reports()

    view = project_dashboard_certification_view(
        view_id="certification-view-1",
        daily_report=daily,
        weekly_report=weekly,
        monthly_report=monthly,
    )

    assert view.daily_report_id == "daily-2"
    assert view.weekly_report_id == "weekly-1"
    assert view.monthly_report_id == "monthly-1"
    assert view.starting_capital == monthly.starting_capital
    assert view.ending_capital == monthly.ending_capital
    assert view.net_pnl == monthly.net_pnl
    assert view.maximum_drawdown_amount == (
        monthly.maximum_drawdown_amount
    )
    assert view.maximum_drawdown_percent == (
        monthly.maximum_drawdown_percent
    )
    assert view.official_prediction_count == 2
    assert view.pending_prediction_count == 0
    assert view.excluded_prediction_count == 0
    assert view.closed_trade_count == 1
    assert view.loss_count == 1
    assert view.incident_count == 1
    assert view.duplicate_attempt_count == 1
    assert dict(view.action_distribution) == {
        "CALL": 1,
        "PUT": 0,
        "WAIT": 1,
    }
    assert {
        key: count
        for key, count in view.outcome_distribution
        if count > 0
    } == {
        "NO_TRADE_CORRECT": 1,
        "STOP_HIT": 1,
    }


def test_projection_keeps_nifty_and_sensex_separate():
    _, daily, weekly, monthly = reports()

    view = project_dashboard_certification_view(
        view_id="certification-view-1",
        daily_report=daily,
        weekly_report=weekly,
        monthly_report=monthly,
    )

    assert tuple(
        item.market
        for item in view.market_views
    ) == ("NIFTY",)
    assert view.market_views[0].prediction_count == 2


def test_projection_rejects_unrelated_period_reports():
    first, daily, weekly, monthly = reports()

    from dataclasses import replace

    unrelated = replace(
        weekly,
        daily_report_ids=("different-daily",),
    )
    with pytest.raises(
        ValueError,
        match="weekly report does not include daily report",
    ):
        project_dashboard_certification_view(
            view_id="certification-view-1",
            daily_report=first,
            weekly_report=unrelated,
            monthly_report=monthly,
        )


