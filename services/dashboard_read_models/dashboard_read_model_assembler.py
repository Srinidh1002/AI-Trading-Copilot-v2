from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ._shared import aware, diagnostics, text
from .dashboard_cycle_view_v1 import DashboardCycleViewV1
from .dashboard_market_state_v1 import DashboardMarketStateV1
from .dashboard_paper_position_view_v1 import DashboardPaperPositionViewV1
from .dashboard_portfolio_view_v1 import DashboardPortfolioViewV1
from .dashboard_runner_health_v1 import DashboardRunnerHealthV1
from .dashboard_system_snapshot_v1 import DashboardSystemSnapshotV1
from .dashboard_validation_summary_v1 import DashboardValidationSummaryV1


_STATUS_PRECEDENCE = {
    "NO_DATA": 0,
    "READY": 1,
    "DEGRADED": 2,
    "BLOCKED": 3,
    "ERROR": 4,
}


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        value = text(value, "diagnostic")
        if value not in result:
            result.append(value)
    return tuple(result)


def _system_status(
    *,
    markets: tuple[DashboardMarketStateV1, ...],
    latest_cycle: DashboardCycleViewV1 | None,
    portfolio: DashboardPortfolioViewV1 | None,
    runner_health: DashboardRunnerHealthV1,
    blockers: tuple[str, ...],
    errors: tuple[str, ...],
    warnings: tuple[str, ...],
) -> str:
    candidates = ["NO_DATA"]

    if markets or latest_cycle is not None or portfolio is not None:
        candidates.append("READY")

    if warnings:
        candidates.append("DEGRADED")

    if blockers:
        candidates.append("BLOCKED")

    if errors:
        candidates.append("ERROR")

    if runner_health.startup_status in {"FAILED", "ERROR"}:
        candidates.append("ERROR")

    if latest_cycle is not None:
        if latest_cycle.cycle_status == "FAILED":
            candidates.append("ERROR")
        elif latest_cycle.cycle_status == "BLOCKED":
            candidates.append("BLOCKED")
        elif latest_cycle.cycle_status == "COMPLETED_NO_ACTION":
            candidates.append("DEGRADED")

    if any(item.blockers for item in markets):
        candidates.append("BLOCKED")

    return max(candidates, key=_STATUS_PRECEDENCE.__getitem__)


@dataclass(frozen=True, slots=True)
class DashboardReadModelAssemblyInputV1:
    snapshot_id: str
    generated_at: datetime
    market_states: tuple[DashboardMarketStateV1, ...]
    positions: tuple[DashboardPaperPositionViewV1, ...]
    runner_health: DashboardRunnerHealthV1
    validation_summary: DashboardValidationSummaryV1
    latest_cycle: DashboardCycleViewV1 | None = None
    portfolio: DashboardPortfolioViewV1 | None = None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "generated_at", aware(self.generated_at, "generated_at"))

        if type(self.market_states) is not tuple:
            raise TypeError("market_states must be an exact tuple")
        if any(type(item) is not DashboardMarketStateV1 for item in self.market_states):
            raise TypeError("market_states contains wrong type")

        if type(self.positions) is not tuple:
            raise TypeError("positions must be an exact tuple")
        if any(type(item) is not DashboardPaperPositionViewV1 for item in self.positions):
            raise TypeError("positions contains wrong type")

        if type(self.runner_health) is not DashboardRunnerHealthV1:
            raise TypeError("runner_health has wrong type")
        if type(self.validation_summary) is not DashboardValidationSummaryV1:
            raise TypeError("validation_summary has wrong type")
        if self.latest_cycle is not None and type(self.latest_cycle) is not DashboardCycleViewV1:
            raise TypeError("latest_cycle has wrong type")
        if self.portfolio is not None and type(self.portfolio) is not DashboardPortfolioViewV1:
            raise TypeError("portfolio has wrong type")

        for name in ("blockers", "warnings", "errors"):
            object.__setattr__(self, name, diagnostics(getattr(self, name), name))


class DashboardReadModelAssembler:
    """Pure deterministic assembly of already-projected dashboard state."""

    def assemble(
        self,
        value: DashboardReadModelAssemblyInputV1,
    ) -> DashboardSystemSnapshotV1:
        if type(value) is not DashboardReadModelAssemblyInputV1:
            raise TypeError(
                "value must be exact DashboardReadModelAssemblyInputV1"
            )

        markets = tuple(
            sorted(
                value.market_states,
                key=lambda item: (item.market, item.symbol),
            )
        )
        positions = tuple(
            sorted(
                value.positions,
                key=lambda item: (
                    item.paper_trade_id,
                    item.trade_plan_id,
                ),
            )
        )

        blockers = _unique(
            value.blockers
            + tuple(
                item
                for market in markets
                for item in market.blockers
            )
            + (
                value.portfolio.blockers
                if value.portfolio is not None
                else ()
            )
            + (
                value.latest_cycle.blockers
                if value.latest_cycle is not None
                else ()
            )
        )

        warnings = _unique(
            value.warnings
            + tuple(
                item
                for market in markets
                for item in market.warnings
            )
            + tuple(
                item
                for position in positions
                for item in position.warnings
            )
            + (
                value.portfolio.warnings
                if value.portfolio is not None
                else ()
            )
            + value.runner_health.warnings
            + value.validation_summary.warnings
            + (
                value.latest_cycle.warnings
                if value.latest_cycle is not None
                else ()
            )
        )

        errors = _unique(
            value.errors
            + value.runner_health.errors
            + (
                value.latest_cycle.errors
                if value.latest_cycle is not None
                else ()
            )
        )

        return DashboardSystemSnapshotV1(
            snapshot_id=value.snapshot_id,
            generated_at=value.generated_at,
            market_states=markets,
            positions=positions,
            runner_health=value.runner_health,
            validation_summary=value.validation_summary,
            latest_cycle=value.latest_cycle,
            portfolio=value.portfolio,
            system_status=_system_status(
                markets=markets,
                latest_cycle=value.latest_cycle,
                portfolio=value.portfolio,
                runner_health=value.runner_health,
                blockers=blockers,
                errors=errors,
                warnings=warnings,
            ),
            blockers=blockers,
            warnings=warnings,
            errors=errors,
        )
