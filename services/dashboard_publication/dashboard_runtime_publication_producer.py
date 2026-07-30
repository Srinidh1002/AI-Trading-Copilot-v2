from __future__ import annotations

from datetime import datetime
from typing import Callable

from services.contracts.integrated_three_target_trade_plan_result_v1 import (
    IntegratedThreeTargetTradePlanResultV1,
)
from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)
from services.contracts.trade_opportunity_v1 import TradeOpportunityV1
from services.dashboard_read_models.dashboard_integrated_trade_plan_projection import (
    project_integrated_three_target_trade_plan,
)
from services.dashboard_read_models import (
    project_paper_trade_position_detail,
    project_trade_opportunity,
)

from .dashboard_publication_envelope_v1 import (
    DashboardPublicationEnvelopeV1,
)
from .dashboard_publication_store import DashboardPublicationStore


Clock = Callable[[], datetime]
PublicationIdFactory = Callable[
    [PaperOrchestrationCycleInputV1, PaperOrchestrationCycleResultV1, int],
    str,
]


def _aware(clock: Clock) -> datetime:
    value = clock()
    if not isinstance(value, datetime):
        raise TypeError("clock must return a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("clock must return a timezone-aware datetime")
    return value


class DashboardRuntimePublicationProducer:
    """Publish coherent runtime sources into the last-known-good store."""

    def __init__(
        self,
        *,
        store: DashboardPublicationStore,
        clock: Clock,
        publication_id_factory: PublicationIdFactory,
    ) -> None:
        if type(store) is not DashboardPublicationStore:
            raise TypeError("store")
        if not callable(clock):
            raise TypeError("clock")
        if not callable(publication_id_factory):
            raise TypeError("publication_id_factory")
        self.store = store
        self.clock = clock
        self.publication_id_factory = publication_id_factory

    def _next_sequence(self) -> int:
        latest = self.store.get_snapshot().latest_envelope
        return 1 if latest is None else latest.publication_sequence + 1

    def publish_cycle(
        self,
        *,
        cycle_input: PaperOrchestrationCycleInputV1,
        cycle_result: PaperOrchestrationCycleResultV1,
        source: str,
    ):
        if type(cycle_input) is not PaperOrchestrationCycleInputV1:
            raise TypeError("cycle_input")
        if type(cycle_result) is not PaperOrchestrationCycleResultV1:
            raise TypeError("cycle_result")
        if source not in {"OPPORTUNITY", "MONITORING"}:
            raise ValueError("unsupported publication source")

        attempted_at = _aware(self.clock)

        if cycle_result.cycle_status == "DUPLICATE_NO_CHANGE":
            return self.store.get_snapshot()

        if cycle_result.cycle_status == "FAILED":
            return self.store.record_failure(
                attempted_at=attempted_at,
                error="; ".join(cycle_result.errors)
                or "PAPER cycle failed",
            )

        try:
            opportunity_source = cycle_input.trade_opportunity
            integrated_source = cycle_input.integrated_trade_plan_result
            p7_source = cycle_input.p7_persistence_snapshot

            if (
                opportunity_source is not None
                and type(opportunity_source) is not TradeOpportunityV1
            ):
                raise TypeError("trade_opportunity")
            if (
                integrated_source is not None
                and type(integrated_source)
                is not IntegratedThreeTargetTradePlanResultV1
            ):
                raise TypeError("integrated_trade_plan_result")
            if (
                p7_source is not None
                and type(p7_source)
                is not PaperTradePersistenceSnapshotV1
            ):
                raise TypeError("p7_persistence_snapshot")

            status = cycle_result.cycle_status
            if status == "BLOCKED":
                publication_status = "BLOCKED"
            elif status == "COMPLETED_NO_ACTION":
                publication_status = "NO_ACTION"
            elif integrated_source is not None and integrated_source.status == "READY":
                publication_status = (
                    "READY_WITH_WARNINGS"
                    if cycle_result.warnings or integrated_source.warnings
                    else "READY"
                )
            elif integrated_source is not None and integrated_source.status == "BLOCKED":
                publication_status = "BLOCKED"
            else:
                publication_status = "NO_ACTION"

            opportunity = (
                project_trade_opportunity(opportunity_source)
                if opportunity_source is not None
                else None
            )
            trade_plan = (
                project_integrated_three_target_trade_plan(
                    integrated_source
                )
                if integrated_source is not None
                else None
            )
            paper_position = (
                project_paper_trade_position_detail(p7_source)
                if p7_source is not None
                else None
            )

            if publication_status == "NO_ACTION":
                trade_plan = None

            blockers = tuple(
                dict.fromkeys(
                    cycle_result.blockers
                    + (
                        tuple(integrated_source.blockers)
                        if integrated_source is not None
                        else ()
                    )
                )
            )
            warnings = tuple(
                dict.fromkeys(
                    cycle_result.warnings
                    + (
                        tuple(integrated_source.warnings)
                        if integrated_source is not None
                        else ()
                    )
                )
            )
            errors = tuple(cycle_result.errors)
            sequence = self._next_sequence()
            publication_id = self.publication_id_factory(
                cycle_input,
                cycle_result,
                sequence,
            )
            source_updated_at = max(
                item
                for item in (
                    cycle_result.completed_at,
                    getattr(p7_source, "updated_at", None),
                    getattr(integrated_source, "canonical_trade_plan_input", None)
                    and getattr(
                        integrated_source.canonical_trade_plan_input,
                        "evaluated_at",
                        None,
                    ),
                )
                if item is not None
            )
            if source_updated_at > attempted_at:
                source_updated_at = attempted_at

            envelope = DashboardPublicationEnvelopeV1(
                publication_id=publication_id,
                publication_sequence=sequence,
                published_at=attempted_at,
                source_updated_at=source_updated_at,
                publication_status=publication_status,
                freshness_status="FRESH",
                cycle_result=cycle_result,
                opportunity=opportunity,
                trade_plan=trade_plan,
                paper_position=paper_position,
                blockers=blockers,
                warnings=warnings,
                errors=errors,
            )
            return self.store.publish(
                envelope,
                attempted_at=attempted_at,
            )
        except Exception as exc:
            return self.store.record_failure(
                attempted_at=attempted_at,
                error=exc,
            )
