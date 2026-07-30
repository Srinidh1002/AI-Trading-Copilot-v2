from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from services.dashboard_read_models import (
    DashboardCycleViewV1,
    DashboardMarketStateV1,
    DashboardPaperPositionViewV1,
    DashboardPortfolioViewV1,
    DashboardRunnerHealthV1,
    DashboardSystemSnapshotV1,
    DashboardValidationSummaryV1,
)


NOW = datetime(2026, 7, 30, 9, 30, tzinfo=timezone.utc)


def runner():
    return DashboardRunnerHealthV1(
        running=False,
        stop_requested=False,
        interrupted=False,
        startup_status="COMPLETED",
        cycles_started=1,
        cycles_completed=1,
        cycles_with_errors=0,
        opportunity_successes=1,
        opportunity_failures=0,
        monitoring_successes=1,
        monitoring_failures=0,
    )


def validation():
    return DashboardValidationSummaryV1(
        completed_trade_count=1,
        winning_trade_count=1,
        losing_trade_count=0,
        breakeven_trade_count=0,
        gross_pnl=100.0,
        net_pnl=90.0,
        win_rate_fraction=1.0,
        average_win=90.0,
        average_loss=None,
        profit_factor=None,
        maximum_win=90.0,
        maximum_loss=None,
        data_status="READY",
    )


def test_market_state_is_frozen_and_paper_only():
    value = DashboardMarketStateV1(
        market="NIFTY",
        symbol="NIFTY",
        observed_at=NOW,
        market_status="OPEN",
        data_status="READY",
        freshness_status="FRESH",
        ltp=25000.0,
    )

    with pytest.raises(FrozenInstanceError):
        value.market = "SENSEX"

    with pytest.raises(ValueError):
        DashboardMarketStateV1(
            market="NIFTY",
            symbol="NIFTY",
            observed_at=NOW,
            market_status="OPEN",
            data_status="READY",
            freshness_status="FRESH",
            execution_mode="LIVE",
        )


def test_cycle_view_rejects_duplicate_stages():
    with pytest.raises(ValueError, match="duplicate stage"):
        DashboardCycleViewV1(
            cycle_result_id="result-1",
            cycle_id="cycle-1",
            cycle_status="COMPLETED",
            terminal_stage="PERSISTENCE",
            started_at=NOW,
            completed_at=NOW,
            stage_statuses=(
                ("DATA", "COMPLETED"),
                ("DATA", "COMPLETED"),
            ),
        )


def test_position_view_rejects_negative_quantity():
    with pytest.raises(ValueError, match="remaining_quantity"):
        DashboardPaperPositionViewV1(
            paper_trade_id="trade-1",
            trade_plan_id="plan-1",
            lifecycle_state="OPEN",
            updated_at=NOW,
            remaining_quantity=-1,
        )


def test_portfolio_view_serializes_stably():
    value = DashboardPortfolioViewV1(
        portfolio_id="portfolio-1",
        trading_day_id="2026-07-30",
        updated_at=NOW,
        starting_capital=100000,
        available_cash=90000,
        reserved_capital=0,
        deployed_capital=10000,
        committed_capital=10000,
        realized_net_pnl=0,
        unrealized_pnl=500,
        total_pnl=500,
        total_equity=100500,
        open_position_count=1,
        pending_plan_count=0,
        concurrent_trade_count=1,
        aggregate_committed_risk=2000,
        event_sequence=1,
    )

    assert value.to_dict()["updated_at"] == NOW.isoformat()
    assert value.to_dict() == value.to_dict()


def test_validation_summary_rejects_inconsistent_counts():
    with pytest.raises(ValueError, match="trade counts"):
        DashboardValidationSummaryV1(
            completed_trade_count=2,
            winning_trade_count=1,
            losing_trade_count=0,
            breakeven_trade_count=0,
            gross_pnl=1,
            net_pnl=1,
            win_rate_fraction=0.5,
            average_win=1,
            average_loss=None,
            profit_factor=None,
            maximum_win=1,
            maximum_loss=None,
            data_status="READY",
        )


def test_system_snapshot_rejects_duplicate_markets():
    market = DashboardMarketStateV1(
        market="NIFTY",
        symbol="NIFTY",
        observed_at=NOW,
        market_status="OPEN",
        data_status="READY",
        freshness_status="FRESH",
    )

    with pytest.raises(ValueError, match="duplicate market"):
        DashboardSystemSnapshotV1(
            snapshot_id="snapshot-1",
            generated_at=NOW,
            market_states=(market, market),
            positions=(),
            runner_health=runner(),
            validation_summary=validation(),
        )


def test_system_snapshot_round_trip_shape_is_json_safe():
    market = DashboardMarketStateV1(
        market="NIFTY",
        symbol="NIFTY",
        observed_at=NOW,
        market_status="OPEN",
        data_status="READY",
        freshness_status="FRESH",
    )
    value = DashboardSystemSnapshotV1(
        snapshot_id="snapshot-1",
        generated_at=NOW,
        market_states=(market,),
        positions=(),
        runner_health=runner(),
        validation_summary=validation(),
        system_status="READY",
    )

    payload = value.to_dict()

    assert payload["generated_at"] == NOW.isoformat()
    assert payload["market_states"][0]["market"] == "NIFTY"
    assert payload["execution_mode"] == "PAPER"
    assert payload["live_execution_eligible"] is False
