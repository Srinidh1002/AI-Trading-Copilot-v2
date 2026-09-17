from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)
from services.contracts.paper_portfolio_persistence_snapshot_v1 import (
    PaperPortfolioPersistenceSnapshotV1,
)
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)
from services.dashboard_read_models import (
    project_cycle_result,
    project_paper_trade_snapshot,
    project_portfolio_snapshot,
    project_runtime_stats,
)


NOW = datetime(2026, 7, 30, 9, 30, tzinfo=timezone.utc)


def exact(cls, **attrs):
    value = object.__new__(cls)
    for name, item in attrs.items():
        object.__setattr__(value, name, item)
    return value


def test_cycle_projection_preserves_authoritative_fields():
    stage = SimpleNamespace(stage="DATA", status="COMPLETED")
    source = exact(
        PaperOrchestrationCycleResultV1,
        cycle_result_id="result-1",
        cycle_id="cycle-1",
        cycle_status="COMPLETED",
        terminal_stage="DATA",
        started_at=NOW,
        completed_at=NOW,
        stage_results=(stage,),
        paper_actions=("NO_ACTION",),
        blockers=(),
        warnings=("warning",),
        errors=(),
        duplicate_of_cycle_result_id=None,
        execution_mode="PAPER",
        live_execution_eligible=False,
    )

    result = project_cycle_result(source)

    assert result.cycle_result_id == "result-1"
    assert result.stage_statuses == (("DATA", "COMPLETED"),)
    assert result.paper_actions == ("NO_ACTION",)
    assert result.warnings == ("warning",)


def test_trade_projection_handles_pending_position():
    lifecycle = SimpleNamespace(
        trade_plan_id="plan-1",
        current_state="WAITING_FOR_ENTRY",
        blockers=(),
        warnings=(),
    )
    source = exact(
        PaperTradePersistenceSnapshotV1,
        paper_trade_id="trade-1",
        lifecycle_state=lifecycle,
        position=None,
        latest_observation=None,
        pnl_evidence=None,
        updated_at=NOW,
        event_sequence=0,
        execution_mode="PAPER",
        live_execution_eligible=False,
    )

    result = project_paper_trade_snapshot(source)

    assert result.paper_trade_id == "trade-1"
    assert result.trade_plan_id == "plan-1"
    assert result.lifecycle_state == "WAITING_FOR_ENTRY"
    assert result.remaining_quantity == 0


def test_trade_projection_combines_pnl_when_total_is_missing():
    lifecycle = SimpleNamespace(
        trade_plan_id="plan-1",
        current_state="OPEN",
        blockers=(),
        warnings=("lifecycle",),
    )
    position = SimpleNamespace(
        position_id="position-1",
        trade_plan_id="plan-1",
        remaining_quantity=25,
        entry_price=100.0,
        market="NIFTY",
        instrument="NIFTY-CE",
        blockers=(),
        warnings=("position",),
    )
    pnl = SimpleNamespace(
        realized_net_pnl=20.0,
        unrealized_pnl=30.0,
        warnings=("pnl",),
    )
    source = exact(
        PaperTradePersistenceSnapshotV1,
        paper_trade_id="trade-1",
        lifecycle_state=lifecycle,
        position=position,
        latest_observation=None,
        pnl_evidence=pnl,
        updated_at=NOW,
        event_sequence=2,
        execution_mode="PAPER",
        live_execution_eligible=False,
    )

    result = project_paper_trade_snapshot(source)

    assert result.remaining_quantity == 25
    assert result.total_pnl == 50.0
    assert result.warnings == (
        "lifecycle",
        "position",
        "pnl",
    )


def test_portfolio_projection_preserves_certified_totals():
    portfolio = SimpleNamespace(
        portfolio_id="portfolio-1",
        trading_day_id="2026-07-30",
        updated_at=NOW,
        starting_capital=100000.0,
        available_cash=90000.0,
        reserved_capital=0.0,
        deployed_capital=10000.0,
        committed_capital=10000.0,
        realized_net_pnl=100.0,
        unrealized_pnl=200.0,
        total_pnl=300.0,
        total_equity=100300.0,
        open_position_count=1,
        pending_plan_count=0,
        concurrent_trade_count=1,
        aggregate_committed_risk=2000.0,
        event_sequence=3,
        blockers=(),
        warnings=("portfolio warning",),
        execution_mode="PAPER",
        live_execution_eligible=False,
    )
    source = exact(
        PaperPortfolioPersistenceSnapshotV1,
        portfolio_snapshot=portfolio,
    )

    result = project_portfolio_snapshot(source)

    assert result.portfolio_id == "portfolio-1"
    assert result.total_equity == 100300.0
    assert result.aggregate_committed_risk == 2000.0
    assert result.warnings == ("portfolio warning",)


def test_runtime_projection_preserves_last_cycle():
    result = project_runtime_stats(
        {
            "running": True,
            "stop_requested": False,
            "interrupted": False,
            "startup_status": "COMPLETED",
            "cycles_started": 2,
            "cycles_completed": 1,
            "cycles_with_errors": 0,
            "opportunity_successes": 1,
            "opportunity_failures": 0,
            "monitoring_successes": 1,
            "monitoring_failures": 0,
            "startup_error": None,
            "last_cycle": {
                "cycle_number": 1,
                "status": "COMPLETED",
                "duration_seconds": 0.25,
            },
        }
    )

    assert result.running is True
    assert result.last_cycle_number == 1
    assert result.last_cycle_status == "COMPLETED"
    assert result.last_cycle_duration_seconds == 0.25


def test_runtime_projection_rejects_incomplete_stats():
    with pytest.raises(
        ValueError,
        match="runtime statistics are incomplete",
    ):
        project_runtime_stats({"running": False})


def test_projection_functions_require_exact_typed_snapshots():
    with pytest.raises(TypeError):
        project_cycle_result(SimpleNamespace())

    with pytest.raises(TypeError):
        project_paper_trade_snapshot(SimpleNamespace())

    with pytest.raises(TypeError):
        project_portfolio_snapshot(SimpleNamespace())
