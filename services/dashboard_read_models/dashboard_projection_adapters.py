from __future__ import annotations

from collections.abc import Mapping

from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)
from services.contracts.paper_portfolio_persistence_snapshot_v1 import (
    PaperPortfolioPersistenceSnapshotV1,
)
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)

from .dashboard_cycle_view_v1 import DashboardCycleViewV1
from .dashboard_paper_position_view_v1 import DashboardPaperPositionViewV1
from .dashboard_portfolio_view_v1 import DashboardPortfolioViewV1
from .dashboard_runner_health_v1 import DashboardRunnerHealthV1


def project_cycle_result(
    value: PaperOrchestrationCycleResultV1,
) -> DashboardCycleViewV1:
    if type(value) is not PaperOrchestrationCycleResultV1:
        raise TypeError(
            "value must be exact PaperOrchestrationCycleResultV1"
        )

    return DashboardCycleViewV1(
        cycle_result_id=value.cycle_result_id,
        cycle_id=value.cycle_id,
        cycle_status=value.cycle_status,
        terminal_stage=value.terminal_stage,
        started_at=value.started_at,
        completed_at=value.completed_at,
        stage_statuses=tuple(
            (item.stage, item.status)
            for item in value.stage_results
        ),
        paper_actions=tuple(value.paper_actions),
        blockers=tuple(value.blockers),
        warnings=tuple(value.warnings),
        errors=tuple(value.errors),
        duplicate_of_cycle_result_id=(
            value.duplicate_of_cycle_result_id
        ),
        execution_mode=value.execution_mode,
        live_execution_eligible=value.live_execution_eligible,
    )


def project_paper_trade_snapshot(
    value: PaperTradePersistenceSnapshotV1,
) -> DashboardPaperPositionViewV1:
    if type(value) is not PaperTradePersistenceSnapshotV1:
        raise TypeError(
            "value must be exact PaperTradePersistenceSnapshotV1"
        )

    lifecycle = value.lifecycle_state
    position = value.position
    pnl = value.pnl_evidence
    observation = value.latest_observation

    trade_plan_id = str(
        getattr(lifecycle, "trade_plan_id", "")
    ).strip()
    if not trade_plan_id and position is not None:
        trade_plan_id = str(
            getattr(position, "trade_plan_id", "")
        ).strip()
    if not trade_plan_id:
        raise ValueError("typed P7 snapshot has no trade_plan_id")

    def optional_text(source, *names):
        if source is None:
            return None
        for name in names:
            candidate = getattr(source, name, None)
            if candidate is not None and str(candidate).strip():
                return str(candidate).strip()
        return None

    def optional_number(source, *names):
        if source is None:
            return None
        for name in names:
            candidate = getattr(source, name, None)
            if candidate is not None:
                return candidate
        return None

    remaining_quantity = 0
    if position is not None:
        candidate = getattr(position, "remaining_quantity", 0)
        remaining_quantity = int(candidate)

    realized = optional_number(
        pnl,
        "realized_net_pnl",
        "net_realized_pnl",
        "realized_pnl",
    )
    unrealized = optional_number(
        pnl,
        "unrealized_pnl",
        "net_unrealized_pnl",
    )
    total = optional_number(
        pnl,
        "total_pnl",
        "combined_pnl",
        "net_total_pnl",
    )
    if total is None and realized is not None and unrealized is not None:
        total = float(realized) + float(unrealized)

    warnings = tuple(
        dict.fromkeys(
            tuple(getattr(lifecycle, "warnings", ()))
            + tuple(
                getattr(position, "warnings", ())
                if position is not None
                else ()
            )
            + tuple(
                getattr(pnl, "warnings", ())
                if pnl is not None
                else ()
            )
        )
    )
    blockers = tuple(
        dict.fromkeys(
            tuple(getattr(lifecycle, "blockers", ()))
            + tuple(
                getattr(position, "blockers", ())
                if position is not None
                else ()
            )
        )
    )

    market = optional_text(
        position,
        "market",
        "underlying",
        "market_symbol",
    )
    instrument = optional_text(
        position,
        "instrument",
        "tradingsymbol",
        "option_symbol",
    )
    if observation is not None:
        market = market or optional_text(
            observation,
            "market",
            "underlying",
            "market_symbol",
        )
        instrument = instrument or optional_text(
            observation,
            "instrument",
            "tradingsymbol",
            "option_symbol",
        )

    return DashboardPaperPositionViewV1(
        paper_trade_id=value.paper_trade_id,
        trade_plan_id=trade_plan_id,
        lifecycle_state=str(lifecycle.current_state),
        updated_at=value.updated_at,
        position_id=optional_text(position, "position_id"),
        market=market,
        instrument=instrument,
        entry_price=optional_number(
            position,
            "entry_price",
            "average_entry_price",
        ),
        remaining_quantity=remaining_quantity,
        realized_net_pnl=realized,
        unrealized_pnl=unrealized,
        total_pnl=total,
        event_sequence=value.event_sequence,
        blockers=blockers,
        warnings=warnings,
        execution_mode=value.execution_mode,
        live_execution_eligible=value.live_execution_eligible,
    )


def project_portfolio_snapshot(
    value: PaperPortfolioPersistenceSnapshotV1,
) -> DashboardPortfolioViewV1:
    if type(value) is not PaperPortfolioPersistenceSnapshotV1:
        raise TypeError(
            "value must be exact PaperPortfolioPersistenceSnapshotV1"
        )

    snapshot = value.portfolio_snapshot

    return DashboardPortfolioViewV1(
        portfolio_id=snapshot.portfolio_id,
        trading_day_id=snapshot.trading_day_id,
        updated_at=snapshot.updated_at,
        starting_capital=snapshot.starting_capital,
        available_cash=snapshot.available_cash,
        reserved_capital=snapshot.reserved_capital,
        deployed_capital=snapshot.deployed_capital,
        committed_capital=snapshot.committed_capital,
        realized_net_pnl=snapshot.realized_net_pnl,
        unrealized_pnl=snapshot.unrealized_pnl,
        total_pnl=snapshot.total_pnl,
        total_equity=snapshot.total_equity,
        open_position_count=snapshot.open_position_count,
        pending_plan_count=snapshot.pending_plan_count,
        concurrent_trade_count=snapshot.concurrent_trade_count,
        aggregate_committed_risk=(
            snapshot.aggregate_committed_risk
        ),
        event_sequence=snapshot.event_sequence,
        blockers=tuple(snapshot.blockers),
        warnings=tuple(snapshot.warnings),
        execution_mode=snapshot.execution_mode,
        live_execution_eligible=snapshot.live_execution_eligible,
    )


def project_runtime_stats(
    value: Mapping[str, object],
) -> DashboardRunnerHealthV1:
    if not isinstance(value, Mapping):
        raise TypeError("value must be a mapping")

    required = {
        "running",
        "stop_requested",
        "interrupted",
        "startup_status",
        "cycles_started",
        "cycles_completed",
        "cycles_with_errors",
        "opportunity_successes",
        "opportunity_failures",
        "monitoring_successes",
        "monitoring_failures",
    }
    missing = required.difference(value)
    if missing:
        raise ValueError(
            "runtime statistics are incomplete: "
            + ", ".join(sorted(missing))
        )

    last_cycle = value.get("last_cycle")
    if last_cycle is not None and not isinstance(last_cycle, Mapping):
        raise TypeError("last_cycle must be a mapping or None")

    startup_error = value.get("startup_error")
    errors = (
        (str(startup_error),)
        if startup_error is not None and str(startup_error).strip()
        else ()
    )

    return DashboardRunnerHealthV1(
        running=value["running"],
        stop_requested=value["stop_requested"],
        interrupted=value["interrupted"],
        startup_status=str(value["startup_status"]),
        cycles_started=value["cycles_started"],
        cycles_completed=value["cycles_completed"],
        cycles_with_errors=value["cycles_with_errors"],
        opportunity_successes=value["opportunity_successes"],
        opportunity_failures=value["opportunity_failures"],
        monitoring_successes=value["monitoring_successes"],
        monitoring_failures=value["monitoring_failures"],
        startup_error=(
            None
            if startup_error is None
            else str(startup_error)
        ),
        last_cycle_status=(
            None
            if last_cycle is None
            else str(last_cycle.get("status"))
        ),
        last_cycle_number=(
            None
            if last_cycle is None
            else last_cycle.get("cycle_number")
        ),
        last_cycle_duration_seconds=(
            None
            if last_cycle is None
            else last_cycle.get("duration_seconds")
        ),
        errors=errors,
    )
