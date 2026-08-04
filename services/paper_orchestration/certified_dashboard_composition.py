from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)
from services.dashboard_publication.dashboard_publication_store import (
    DashboardPublicationStore,
)
from services.dashboard_publication.dashboard_runtime_publication_producer import (
    DashboardRuntimePublicationProducer,
)


Clock = Callable[[], datetime]


def _publication_id(
    cycle_input: PaperOrchestrationCycleInputV1,
    cycle_result: PaperOrchestrationCycleResultV1,
    sequence: int,
) -> str:
    if type(cycle_input) is not PaperOrchestrationCycleInputV1:
        raise TypeError("cycle_input")
    if type(cycle_result) is not PaperOrchestrationCycleResultV1:
        raise TypeError("cycle_result")
    if type(sequence) is not int or isinstance(sequence, bool) or sequence < 1:
        raise ValueError("sequence must be a positive integer")

    payload = "|".join(
        (
            cycle_input.cycle_id,
            cycle_result.cycle_result_id,
            str(sequence),
            "PAPER",
        )
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"dashboard-publication-{digest}"


@dataclass(frozen=True, slots=True)
class CertifiedDashboardPublicationCompositionV1:
    store: DashboardPublicationStore
    producer: DashboardRuntimePublicationProducer
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = (
        "certified_dashboard_publication_composition.v1"
    )

    def __post_init__(self) -> None:
        if type(self.store) is not DashboardPublicationStore:
            raise TypeError("store")
        if type(self.producer) is not DashboardRuntimePublicationProducer:
            raise TypeError("producer")
        if self.producer.store is not self.store:
            raise ValueError("producer/store identity mismatch")
        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible:
            raise ValueError("live execution is not eligible")
        if self.schema_version != (
            "certified_dashboard_publication_composition.v1"
        ):
            raise ValueError("unsupported schema_version")


def build_certified_dashboard_publication(
    *,
    clock: Clock,
) -> CertifiedDashboardPublicationCompositionV1:
    if not callable(clock):
        raise TypeError("clock must be callable")

    store = DashboardPublicationStore()
    producer = DashboardRuntimePublicationProducer(
        store=store,
        clock=clock,
        publication_id_factory=_publication_id,
    )
    return CertifiedDashboardPublicationCompositionV1(
        store=store,
        producer=producer,
    )
