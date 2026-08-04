from datetime import datetime, timezone

import pytest

from services.dashboard_read_models import (
    DashboardCycleViewV1,
    DashboardMarketStateV1,
    DashboardPaperPositionViewV1,
    DashboardReadModelAssembler,
    DashboardReadModelAssemblyInputV1,
    DashboardRunnerHealthV1,
    DashboardValidationSummaryV1,
)


NOW = datetime(2026, 7, 30, 9, 30, tzinfo=timezone.utc)


def runner(
    *,
    startup_status: str = "COMPLETED",
    warnings: tuple[str, ...] = (),
    errors: tuple[str, ...] = (),
):
    return DashboardRunnerHealthV1(
        running=False,
        stop_requested=False,
        interrupted=False,
        startup_status=startup_status,
        cycles_started=1,
        cycles_completed=1,
        cycles_with_errors=0,
        opportunity_successes=1,
        opportunity_failures=0,
        monitoring_successes=1,
        monitoring_failures=0,
        warnings=warnings,
        errors=errors,
    )


def validation(
    *,
    warnings: tuple[str, ...] = (),
):
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
        warnings=warnings,
    )


def market(
    name: str,
    *,
    warnings: tuple[str, ...] = (),
    blockers: tuple[str, ...] = (),
):
    return DashboardMarketStateV1(
        market=name,
        symbol=name,
        observed_at=NOW,
        market_status="OPEN",
        data_status="READY",
        freshness_status="FRESH",
        warnings=warnings,
        blockers=blockers,
    )


def position(trade_id: str):
    return DashboardPaperPositionViewV1(
        paper_trade_id=trade_id,
        trade_plan_id=f"plan-{trade_id}",
        lifecycle_state="OPEN",
        updated_at=NOW,
    )


def cycle(status: str):
    stage_status = (
        "FAILED"
        if status == "FAILED"
        else "BLOCKED"
        if status == "BLOCKED"
        else "COMPLETED"
    )
    return DashboardCycleViewV1(
        cycle_result_id="result-1",
        cycle_id="cycle-1",
        cycle_status=status,
        terminal_stage="PERSISTENCE",
        started_at=NOW,
        completed_at=NOW,
        stage_statuses=(("PERSISTENCE", stage_status),),
        errors=("cycle failed",) if status == "FAILED" else (),
        blockers=("cycle blocked",) if status == "BLOCKED" else (),
    )


def assemble(**overrides):
    values = dict(
        snapshot_id="snapshot-1",
        generated_at=NOW,
        market_states=(),
        positions=(),
        runner_health=runner(),
        validation_summary=validation(),
    )
    values.update(overrides)
    return DashboardReadModelAssembler().assemble(
        DashboardReadModelAssemblyInputV1(**values)
    )


def test_empty_assembly_is_no_data():
    result = assemble()

    assert result.system_status == "NO_DATA"
    assert result.market_states == ()
    assert result.positions == ()


def test_assembly_sorts_markets_and_positions_deterministically():
    result = assemble(
        market_states=(market("SENSEX"), market("NIFTY")),
        positions=(position("trade-2"), position("trade-1")),
    )

    assert tuple(item.market for item in result.market_states) == (
        "NIFTY",
        "SENSEX",
    )
    assert tuple(item.paper_trade_id for item in result.positions) == (
        "trade-1",
        "trade-2",
    )


def test_assembly_deduplicates_diagnostics_preserving_order():
    result = assemble(
        market_states=(
            market("NIFTY", warnings=("stale", "stale")),
        ),
        warnings=("caller", "stale"),
        runner_health=runner(warnings=("runner", "caller")),
        validation_summary=validation(warnings=("validation",)),
    )

    assert result.warnings == (
        "caller",
        "stale",
        "runner",
        "validation",
    )


def test_error_precedence_over_blocked_and_degraded():
    result = assemble(
        market_states=(
            market(
                "NIFTY",
                warnings=("warning",),
                blockers=("blocked",),
            ),
        ),
        errors=("fatal",),
    )

    assert result.system_status == "ERROR"


def test_blocked_cycle_produces_blocked_status():
    result = assemble(
        latest_cycle=cycle("BLOCKED"),
    )

    assert result.system_status == "BLOCKED"
    assert result.blockers == ("cycle blocked",)


def test_failed_startup_produces_error_status():
    result = assemble(
        runner_health=runner(
            startup_status="FAILED",
            errors=("startup failed",),
        ),
    )

    assert result.system_status == "ERROR"
    assert result.errors == ("startup failed",)


def test_assembler_rejects_wrong_input_type():
    with pytest.raises(TypeError):
        DashboardReadModelAssembler().assemble(object())
