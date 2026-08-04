from datetime import datetime, timezone
from types import SimpleNamespace

from services.dashboard_publication import DashboardPublicationStore
from services.dashboard_publication.dashboard_runtime_publication_producer import (
    DashboardRuntimePublicationProducer,
)


NOW = datetime(2026, 7, 30, 15, 0, tzinfo=timezone.utc)


def producer(store):
    return DashboardRuntimePublicationProducer(
        store=store,
        clock=lambda: NOW,
        publication_id_factory=lambda cycle_input, cycle_result, sequence: (
            f"{cycle_result.cycle_result_id}:dashboard:{sequence}"
        ),
    )


def test_failed_cycle_records_failure_without_publication():
    store = DashboardPublicationStore()
    value = producer(store)

    cycle_input = object.__new__(
        __import__(
            "services.contracts.paper_orchestration_cycle_input_v1",
            fromlist=["PaperOrchestrationCycleInputV1"],
        ).PaperOrchestrationCycleInputV1
    )
    cycle_result_type = __import__(
        "services.contracts.paper_orchestration_cycle_result_v1",
        fromlist=["PaperOrchestrationCycleResultV1"],
    ).PaperOrchestrationCycleResultV1
    cycle_result = object.__new__(cycle_result_type)
    for name, item in {
        "cycle_status": "FAILED",
        "errors": ("CYCLE_FAILED",),
    }.items():
        object.__setattr__(cycle_result, name, item)

    snapshot = value.publish_cycle(
        cycle_input=cycle_input,
        cycle_result=cycle_result,
        source="OPPORTUNITY",
    )

    assert snapshot.latest_envelope is None
    assert snapshot.failed_attempt_count == 1
    assert snapshot.last_attempt_error == "CYCLE_FAILED"


def test_duplicate_cycle_is_non_destructive():
    store = DashboardPublicationStore()
    value = producer(store)

    input_type = __import__(
        "services.contracts.paper_orchestration_cycle_input_v1",
        fromlist=["PaperOrchestrationCycleInputV1"],
    ).PaperOrchestrationCycleInputV1
    result_type = __import__(
        "services.contracts.paper_orchestration_cycle_result_v1",
        fromlist=["PaperOrchestrationCycleResultV1"],
    ).PaperOrchestrationCycleResultV1
    cycle_input = object.__new__(input_type)
    cycle_result = object.__new__(result_type)
    object.__setattr__(cycle_result, "cycle_status", "DUPLICATE_NO_CHANGE")

    snapshot = value.publish_cycle(
        cycle_input=cycle_input,
        cycle_result=cycle_result,
        source="MONITORING",
    )

    assert snapshot.latest_envelope is None
    assert snapshot.last_attempt_status == "NOT_ATTEMPTED"
