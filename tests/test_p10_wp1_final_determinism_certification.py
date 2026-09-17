from datetime import datetime, timezone

from services.dashboard_read_models import (
    DashboardMarketStateV1,
    DashboardPaperPositionViewV1,
    DashboardReadModelAssembler,
    DashboardReadModelAssemblyInputV1,
    DashboardRunnerHealthV1,
    DashboardValidationSummaryV1,
)


NOW = datetime(2026, 7, 30, 9, 30, tzinfo=timezone.utc)


def runner():
    return DashboardRunnerHealthV1(
        running=False,
        stop_requested=False,
        interrupted=False,
        startup_status="COMPLETED",
        cycles_started=2,
        cycles_completed=2,
        cycles_with_errors=0,
        opportunity_successes=2,
        opportunity_failures=0,
        monitoring_successes=2,
        monitoring_failures=0,
    )


def validation():
    return DashboardValidationSummaryV1(
        completed_trade_count=0,
        winning_trade_count=0,
        losing_trade_count=0,
        breakeven_trade_count=0,
        gross_pnl=0,
        net_pnl=0,
        win_rate_fraction=0,
        average_win=None,
        average_loss=None,
        profit_factor=None,
        maximum_win=None,
        maximum_loss=None,
        data_status="NO_DATA",
    )


def market(name: str):
    return DashboardMarketStateV1(
        market=name,
        symbol=name,
        observed_at=NOW,
        market_status="OPEN",
        data_status="READY",
        freshness_status="FRESH",
    )


def position(trade_id: str):
    return DashboardPaperPositionViewV1(
        paper_trade_id=trade_id,
        trade_plan_id=f"plan-{trade_id}",
        lifecycle_state="OPEN",
        updated_at=NOW,
    )


def assemble(markets, positions):
    return DashboardReadModelAssembler().assemble(
        DashboardReadModelAssemblyInputV1(
            snapshot_id="snapshot-1",
            generated_at=NOW,
            market_states=markets,
            positions=positions,
            runner_health=runner(),
            validation_summary=validation(),
        )
    )


def test_equivalent_input_order_produces_identical_serialization():
    first = assemble(
        (market("SENSEX"), market("NIFTY")),
        (position("trade-2"), position("trade-1")),
    )
    second = assemble(
        (market("NIFTY"), market("SENSEX")),
        (position("trade-1"), position("trade-2")),
    )

    assert first == second
    assert first.to_dict() == second.to_dict()


def test_assembler_does_not_mutate_input_tuples():
    markets = (market("SENSEX"), market("NIFTY"))
    positions = (position("trade-2"), position("trade-1"))
    original_markets = tuple(markets)
    original_positions = tuple(positions)

    result = assemble(markets, positions)

    assert markets == original_markets
    assert positions == original_positions
    assert tuple(item.market for item in result.market_states) == (
        "NIFTY",
        "SENSEX",
    )


def test_snapshot_identity_and_time_are_preserved_exactly():
    value = assemble((market("NIFTY"),), ())

    assert value.snapshot_id == "snapshot-1"
    assert value.generated_at is NOW
