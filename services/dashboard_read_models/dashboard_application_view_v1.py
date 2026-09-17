"""Unified immutable, read-only publication view for the Task 9 dashboard."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar

from services.contracts.task9_live_paper_certification_progress_v1 import (
    Task9LivePaperCertificationProgressV1,
)

from ._shared import aware, exact_tuple, paper_only, plain, text
from .dashboard_decision_history_view_v1 import DashboardDecisionHistoryViewV1
from .dashboard_market_state_v1 import DashboardMarketStateV1
from .dashboard_opportunity_view_v1 import DashboardOpportunityViewV1
from .dashboard_paper_position_detail_view_v1 import (
    DashboardPaperPositionDetailViewV1,
)
from .dashboard_portfolio_view_v1 import DashboardPortfolioViewV1
from .dashboard_runtime_operations_view_v1 import (
    DashboardRuntimeOperationsViewV1,
)
from .dashboard_trade_plan_view_v1 import DashboardTradePlanViewV1


@dataclass(frozen=True, slots=True)
class DashboardManualLivePlannerStateV1:
    """Future manual-live planner boundary; deliberately contains no capital."""

    status: str
    notice: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "status",
            text(self.status, "status"),
        )
        object.__setattr__(
            self,
            "notice",
            text(self.notice, "notice"),
        )


@dataclass(frozen=True, slots=True)
class DashboardApplicationViewV1:
    """Composition-only view: its sources are projected before publication."""

    view_id: str
    generated_at: datetime
    market_session_state: str
    nifty_market: DashboardMarketStateV1 | None = None
    sensex_market: DashboardMarketStateV1 | None = None
    selected_market: str | None = None
    selected_market_rationale: tuple[str, ...] = ()
    rejected_market_rationale: tuple[str, ...] = ()
    primary_opportunity: DashboardOpportunityViewV1 | None = None
    primary_trade_plan: DashboardTradePlanViewV1 | None = None
    active_paper_position: DashboardPaperPositionDetailViewV1 | None = None
    portfolio: DashboardPortfolioViewV1 | None = None
    paper_trade_history: tuple[DashboardPaperPositionDetailViewV1, ...] = ()
    recommendation_history: DashboardDecisionHistoryViewV1 | None = None
    task9_certification_progress: Task9LivePaperCertificationProgressV1 | None = None
    runtime_operations: DashboardRuntimeOperationsViewV1 | None = None
    manual_live_planner: DashboardManualLivePlannerStateV1 | None = None
    external_provider_blocker: Mapping[str, Any] | None = None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    read_only: bool = True

    SCHEMA_VERSION: ClassVar[str] = "dashboard_application_view.v1"
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "view_id",
            text(self.view_id, "view_id"),
        )
        object.__setattr__(
            self,
            "generated_at",
            aware(self.generated_at, "generated_at"),
        )
        object.__setattr__(
            self,
            "market_session_state",
            text(
                self.market_session_state,
                "market_session_state",
            ),
        )

        if self.selected_market is not None:
            selected = text(
                self.selected_market,
                "selected_market",
            ).upper()

            if selected not in {"NIFTY", "SENSEX"}:
                raise ValueError("selected_market")

            object.__setattr__(
                self,
                "selected_market",
                selected,
            )

        optional = (
            (
                self.nifty_market,
                DashboardMarketStateV1,
                "nifty_market",
            ),
            (
                self.sensex_market,
                DashboardMarketStateV1,
                "sensex_market",
            ),
            (
                self.primary_opportunity,
                DashboardOpportunityViewV1,
                "primary_opportunity",
            ),
            (
                self.primary_trade_plan,
                DashboardTradePlanViewV1,
                "primary_trade_plan",
            ),
            (
                self.active_paper_position,
                DashboardPaperPositionDetailViewV1,
                "active_paper_position",
            ),
            (
                self.portfolio,
                DashboardPortfolioViewV1,
                "portfolio",
            ),
            (
                self.recommendation_history,
                DashboardDecisionHistoryViewV1,
                "recommendation_history",
            ),
            (
                self.task9_certification_progress,
                Task9LivePaperCertificationProgressV1,
                "task9_certification_progress",
            ),
            (
                self.runtime_operations,
                DashboardRuntimeOperationsViewV1,
                "runtime_operations",
            ),
            (
                self.manual_live_planner,
                DashboardManualLivePlannerStateV1,
                "manual_live_planner",
            ),
        )

        for value, expected, name in optional:
            if (
                value is not None
                and type(value) is not expected
            ):
                raise TypeError(name)

        if (
            self.nifty_market is not None
            and self.nifty_market.market.upper() != "NIFTY"
        ):
            raise ValueError("nifty_market")

        if (
            self.sensex_market is not None
            and self.sensex_market.market.upper() != "SENSEX"
        ):
            raise ValueError("sensex_market")

        if (
            self.primary_trade_plan is not None
            and self.primary_opportunity is None
        ):
            raise ValueError(
                "primary_trade_plan requires primary_opportunity"
            )

        if (
            self.primary_trade_plan is not None
            and self.primary_trade_plan.selected_opportunity_id
            != self.primary_opportunity.opportunity_id
        ):
            raise ValueError(
                "primary recommendation identity mismatch"
            )

        if (
            self.selected_market is not None
            and self.primary_trade_plan is not None
            and self.selected_market
            != self.primary_trade_plan.market.upper()
        ):
            raise ValueError("selected_market")

        history = exact_tuple(
            self.paper_trade_history,
            "paper_trade_history",
        )

        if any(
            type(item) is not DashboardPaperPositionDetailViewV1
            for item in history
        ):
            raise TypeError("paper_trade_history")

        if len(
            {
                item.paper_trade_id
                for item in history
            }
        ) != len(history):
            raise ValueError(
                "duplicate paper_trade_history"
            )

        object.__setattr__(
            self,
            "paper_trade_history",
            history,
        )

        for name in (
            "selected_market_rationale",
            "rejected_market_rationale",
            "blockers",
            "warnings",
        ):
            values = exact_tuple(
                getattr(self, name),
                name,
            )

            object.__setattr__(
                self,
                name,
                tuple(
                    dict.fromkeys(
                        text(item, name)
                        for item in values
                    )
                ),
            )

        paper_only(
            self.execution_mode,
            self.live_execution_eligible,
        )

        if (
            self.broker_order_submission is not False
            or self.read_only is not True
        ):
            raise ValueError(
                "dashboard application view must remain read-only PAPER"
            )

        if self.schema_version != self.SCHEMA_VERSION:
            raise ValueError(
                "unsupported schema_version"
            )

        if self.external_provider_blocker is not None:
            if not isinstance(
                self.external_provider_blocker,
                Mapping,
            ):
                raise TypeError(
                    "external_provider_blocker"
                )

            legacy_allowed = {
                "blocker_code",
                "status",
                "provider",
                "endpoint",
                "first_seen_at",
                "last_seen_at",
                "last_probe_at",
                "last_probe_result",
                "next_probe_not_before",
                "occurrence_count",
            }

            allowed = legacy_allowed | {
                "last_failure_reason",
                "consecutive_rate_limit_count",
            }

            blocker_keys = set(
                self.external_provider_blocker
            )

            if (
                blocker_keys != legacy_allowed
                and blocker_keys != allowed
            ):
                raise ValueError(
                    "external_provider_blocker"
                )

            object.__setattr__(
                self,
                "external_provider_blocker",
                dict(
                    self.external_provider_blocker
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            name: plain(
                getattr(self, name)
            )
            for name
            in self.__dataclass_fields__
        }