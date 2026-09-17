"""Immutable display-only summary of certified NIFTY/SENSEX runtime evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from ._shared import aware, diagnostics, text


_MARKETS = frozenset({"NIFTY", "SENSEX"})


def _optional_text(value: object, name: str) -> str | None:
    return None if value is None else text(value, name)


@dataclass(frozen=True, slots=True)
class DashboardTwoMarketRuntimeViewV1:
    source_id: str
    source_updated_at: datetime
    runtime_safety_status: str
    provider_freshness_status: str
    nifty_status: str
    sensex_status: str
    emergency_halt: bool
    broker_order_submission: bool
    selected_market: str | None = None
    latest_opportunity_status: str | None = None
    latest_p6_plan_status: str | None = None
    pending_p7_entry_count: int = 0
    open_p7_position_count: int = 0
    p8_portfolio_status: str | None = None
    latest_paper_actions: tuple[str, ...] = ()
    last_successful_cycle_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_failure: str | None = None
    warnings: tuple[str, ...] = ()

    execution_mode: ClassVar[str] = "PAPER"
    live_execution_eligible: ClassVar[bool] = False
    schema_version: ClassVar[str] = "dashboard_two_market_runtime_view.v1"

    def __post_init__(self) -> None:
        for name in (
            "source_id",
            "runtime_safety_status",
            "provider_freshness_status",
            "nifty_status",
            "sensex_status",
        ):
            object.__setattr__(self, name, text(getattr(self, name), name))
        object.__setattr__(self, "source_updated_at", aware(self.source_updated_at, "source_updated_at"))
        if type(self.emergency_halt) is not bool:
            raise TypeError("emergency_halt must be bool")
        if self.broker_order_submission is not False:
            raise ValueError("broker_order_submission must remain false")
        for name in ("pending_p7_entry_count", "open_p7_position_count"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative exact int")
        selected = _optional_text(self.selected_market, "selected_market")
        if selected is not None:
            selected = selected.upper()
            if selected not in _MARKETS:
                raise ValueError("selected_market must be NIFTY or SENSEX")
        object.__setattr__(self, "selected_market", selected)
        for name in ("latest_opportunity_status", "latest_p6_plan_status", "p8_portfolio_status", "last_failure"):
            object.__setattr__(self, name, _optional_text(getattr(self, name), name))
        for name in ("last_successful_cycle_at", "last_failure_at"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, aware(value, name))
        object.__setattr__(self, "latest_paper_actions", diagnostics(self.latest_paper_actions, "latest_paper_actions"))
        object.__setattr__(self, "warnings", diagnostics(self.warnings, "warnings"))

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "source_updated_at": self.source_updated_at.isoformat(),
            "runtime_safety_status": self.runtime_safety_status,
            "provider_freshness_status": self.provider_freshness_status,
            "nifty_status": self.nifty_status,
            "sensex_status": self.sensex_status,
            "selected_market": self.selected_market,
            "latest_opportunity_status": self.latest_opportunity_status,
            "latest_p6_plan_status": self.latest_p6_plan_status,
            "pending_p7_entry_count": self.pending_p7_entry_count,
            "open_p7_position_count": self.open_p7_position_count,
            "p8_portfolio_status": self.p8_portfolio_status,
            "latest_paper_actions": list(self.latest_paper_actions),
            "last_successful_cycle_at": self.last_successful_cycle_at.isoformat() if self.last_successful_cycle_at else None,
            "last_failure_at": self.last_failure_at.isoformat() if self.last_failure_at else None,
            "last_failure": self.last_failure,
            "emergency_halt": self.emergency_halt,
            "broker_order_submission": self.broker_order_submission,
            "execution_mode": self.execution_mode,
            "live_execution_eligible": self.live_execution_eligible,
            "warnings": list(self.warnings),
            "schema_version": self.schema_version,
        }
