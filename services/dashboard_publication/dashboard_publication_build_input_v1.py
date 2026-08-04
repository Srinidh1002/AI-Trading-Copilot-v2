from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)
from services.contracts.three_target_trade_plan_v1 import (
    ThreeTargetTradePlanV1,
)
from services.contracts.trade_opportunity_v1 import TradeOpportunityV1


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


@dataclass(frozen=True, slots=True)
class DashboardPublicationBuildInputV1:
    publication_id: str
    publication_sequence: int
    published_at: datetime
    source_updated_at: datetime
    publication_status: str
    freshness_status: str
    trade_opportunity: TradeOpportunityV1 | None = None
    trade_plan: ThreeTargetTradePlanV1 | None = None
    p7_snapshot: PaperTradePersistenceSnapshotV1 | None = None
    cycle_result: PaperOrchestrationCycleResultV1 | None = None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    execution_mode: ClassVar[str] = "PAPER"
    live_execution_eligible: ClassVar[bool] = False
    schema_version: ClassVar[str] = (
        "dashboard_publication_build_input.v1"
    )

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

        for name in ("publication_status", "freshness_status"):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name).upper(),
            )

        exact = (
            (
                self.trade_opportunity,
                TradeOpportunityV1,
                "trade_opportunity",
            ),
            (
                self.trade_plan,
                ThreeTargetTradePlanV1,
                "trade_plan",
            ),
            (
                self.p7_snapshot,
                PaperTradePersistenceSnapshotV1,
                "p7_snapshot",
            ),
            (
                self.cycle_result,
                PaperOrchestrationCycleResultV1,
                "cycle_result",
            ),
        )
        for value, expected, name in exact:
            if value is not None and type(value) is not expected:
                raise TypeError(
                    f"{name} must be exact {expected.__name__} or None"
                )

        for name in ("blockers", "warnings", "errors"):
            value = getattr(self, name)
            if not isinstance(value, tuple):
                raise TypeError(f"{name} must be a tuple")
            normalized = tuple(
                _text(item, f"{name} item")
                for item in value
            )
            object.__setattr__(self, name, normalized)
