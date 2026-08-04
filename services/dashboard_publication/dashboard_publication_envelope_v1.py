from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)
from services.dashboard_read_models import (
    DashboardOpportunityViewV1,
    DashboardPaperPositionDetailViewV1,
    DashboardTradePlanViewV1,
)
from services.dashboard_read_models.dashboard_option_intelligence_view_v1 import (
    DashboardOptionIntelligenceViewV1,
)
from services.dashboard_read_models.dashboard_runtime_operations_view_v1 import (
    DashboardRuntimeOperationsViewV1,
)


_PUBLICATION_STATUSES = frozenset(
    {
        "READY",
        "READY_WITH_WARNINGS",
        "NO_ACTION",
        "BLOCKED",
        "STALE",
    }
)
_FRESHNESS_STATUSES = frozenset({"FRESH", "STALE", "UNKNOWN"})


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")
    return value.strip()


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _tuple_text(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be a tuple")
    result: list[str] = []
    for item in value:
        normalized = _text(item, f"{name} item")
        if normalized not in result:
            result.append(normalized)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class DashboardPublicationEnvelopeV1:
    publication_id: str
    publication_sequence: int
    published_at: datetime
    source_updated_at: datetime
    publication_status: str
    freshness_status: str
    cycle_result: PaperOrchestrationCycleResultV1 | None = None
    opportunity: DashboardOpportunityViewV1 | None = None
    trade_plan: DashboardTradePlanViewV1 | None = None
    paper_position: DashboardPaperPositionDetailViewV1 | None = None
    option_intelligence: DashboardOptionIntelligenceViewV1 | None = None
    runtime_operations: DashboardRuntimeOperationsViewV1 | None = None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    execution_mode: ClassVar[str] = "PAPER"
    live_execution_eligible: ClassVar[bool] = False
    schema_version: ClassVar[str] = "dashboard_publication_envelope.v1"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "publication_id",
            _text(self.publication_id, "publication_id"),
        )

        if (
            type(self.publication_sequence) is not int
            or isinstance(self.publication_sequence, bool)
        ):
            raise TypeError("publication_sequence must be an exact int")
        if self.publication_sequence <= 0:
            raise ValueError("publication_sequence must be positive")

        published_at = _aware(self.published_at, "published_at")
        source_updated_at = _aware(
            self.source_updated_at,
            "source_updated_at",
        )
        if source_updated_at > published_at:
            raise ValueError(
                "source_updated_at cannot be later than published_at"
            )
        object.__setattr__(self, "published_at", published_at)
        object.__setattr__(self, "source_updated_at", source_updated_at)

        status = _text(
            self.publication_status,
            "publication_status",
        ).upper()
        freshness = _text(
            self.freshness_status,
            "freshness_status",
        ).upper()
        if status not in _PUBLICATION_STATUSES:
            raise ValueError("unsupported publication_status")
        if freshness not in _FRESHNESS_STATUSES:
            raise ValueError("unsupported freshness_status")
        if status == "STALE" and freshness != "STALE":
            raise ValueError(
                "STALE publication requires STALE freshness"
            )
        object.__setattr__(self, "publication_status", status)
        object.__setattr__(self, "freshness_status", freshness)

        exact_optional = (
            (
                self.cycle_result,
                PaperOrchestrationCycleResultV1,
                "cycle_result",
            ),
            (
                self.opportunity,
                DashboardOpportunityViewV1,
                "opportunity",
            ),
            (
                self.trade_plan,
                DashboardTradePlanViewV1,
                "trade_plan",
            ),
            (
                self.paper_position,
                DashboardPaperPositionDetailViewV1,
                "paper_position",
            ),
            (
                self.option_intelligence,
                DashboardOptionIntelligenceViewV1,
                "option_intelligence",
            ),
            (
                self.runtime_operations,
                DashboardRuntimeOperationsViewV1,
                "runtime_operations",
            ),
        )
        for value, expected, name in exact_optional:
            if value is not None and type(value) is not expected:
                raise TypeError(
                    f"{name} must be exact {expected.__name__} or None"
                )

        if self.trade_plan is not None and self.opportunity is None:
            raise ValueError(
                "trade_plan requires opportunity"
            )
        if (
            self.trade_plan is not None
            and self.trade_plan.selected_opportunity_id
            != self.opportunity.opportunity_id
        ):
            raise ValueError(
                "opportunity and trade_plan identity mismatch"
            )
        if (
            self.paper_position is not None
            and self.trade_plan is not None
            and self.paper_position.trade_plan_id
            != self.trade_plan.trade_plan_id
        ):
            raise ValueError(
                "trade_plan and paper_position identity mismatch"
            )

        if status in {"READY", "READY_WITH_WARNINGS"}:
            if self.opportunity is None or self.trade_plan is None:
                raise ValueError(
                    "READY publication requires opportunity and trade_plan"
                )
        if status == "NO_ACTION" and self.trade_plan is not None:
            raise ValueError(
                "NO_ACTION publication cannot contain trade_plan"
            )
        if status == "BLOCKED" and not self.blockers:
            raise ValueError(
                "BLOCKED publication requires blockers"
            )

        blockers = _tuple_text(self.blockers, "blockers")
        warnings = _tuple_text(self.warnings, "warnings")
        errors = _tuple_text(self.errors, "errors")
        if status == "READY_WITH_WARNINGS" and not warnings:
            raise ValueError(
                "READY_WITH_WARNINGS requires warnings"
            )
        object.__setattr__(self, "blockers", blockers)
        object.__setattr__(self, "warnings", warnings)
        object.__setattr__(self, "errors", errors)

    def to_dict(self) -> dict[str, object]:
        return {
            "publication_id": self.publication_id,
            "publication_sequence": self.publication_sequence,
            "published_at": self.published_at.isoformat(),
            "source_updated_at": self.source_updated_at.isoformat(),
            "publication_status": self.publication_status,
            "freshness_status": self.freshness_status,
            "cycle_result": (
                self.cycle_result.to_dict()
                if self.cycle_result is not None
                else None
            ),
            "opportunity": (
                self.opportunity.to_dict()
                if self.opportunity is not None
                else None
            ),
            "trade_plan": (
                self.trade_plan.to_dict()
                if self.trade_plan is not None
                else None
            ),
            "paper_position": (
                self.paper_position.to_dict()
                if self.paper_position is not None
                else None
            ),
            "option_intelligence": (
                self.option_intelligence.to_dict()
                if self.option_intelligence is not None
                else None
            ),
            "runtime_operations": (
                self.runtime_operations.to_dict()
                if self.runtime_operations is not None
                else None
            ),
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "execution_mode": self.execution_mode,
            "live_execution_eligible": self.live_execution_eligible,
            "schema_version": self.schema_version,
        }
