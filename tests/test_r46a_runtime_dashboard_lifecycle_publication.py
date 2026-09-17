from datetime import datetime, timezone

from dashboard.dashboard_publication_sync import (
    synchronize_dashboard_publication,
)
from dashboard.r4_paper_lifecycle_components import (
    R4_PAPER_LIFECYCLE_VIEW_STATE_KEY,
)
from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)
from services.dashboard_publication import (
    DashboardPublicationEnvelopeV1,
    DashboardPublicationSnapshotV1,
    DashboardPublicationStore,
)
from services.dashboard_publication.dashboard_runtime_publication_producer import (
    DashboardRuntimePublicationProducer,
)
from services.dashboard_read_models.r4_paper_lifecycle_dashboard_view_v1 import (
    R4PaperLifecycleDashboardViewV1,
)


NOW = datetime(2026, 8, 5, 5, 0, tzinfo=timezone.utc)


def lifecycle_view():
    return R4PaperLifecycleDashboardViewV1(
        portfolio_id="portfolio-1",
        paper_trade_id="trade-1",
        position_id="position-1",
        underlying_symbol="NIFTY",
        option_symbol="NIFTY-CE",
        lifecycle_state="OPEN",
        reservation_status="ACTIVE",
        initial_quantity=75,
        remaining_quantity=75,
        entry_price=100.0,
        current_option_price=105.0,
        realized_net_pnl=0.0,
        unrealized_pnl=375.0,
        total_pnl=375.0,
        remaining_capital_amount=7500.0,
        remaining_risk_amount=750.0,
        latest_observation_id="observation-1",
        latest_observation_at=NOW,
        entry_fill_id="entry-fill-1",
        exit_fill_ids=(),
        restart_status="RECOVERED",
        reconciliation_status="RECONCILED",
        duplicate_protection_verified=True,
        updated_at=NOW,
    )


def test_envelope_accepts_and_serializes_r4_lifecycle_view():
    view = lifecycle_view()

    envelope = DashboardPublicationEnvelopeV1(
        publication_id="publication-1",
        publication_sequence=1,
        published_at=NOW,
        source_updated_at=NOW,
        publication_status="NO_ACTION",
        freshness_status="FRESH",
        r4_paper_lifecycle=view,
    )

    assert envelope.r4_paper_lifecycle is view
    assert (
        envelope.to_dict()["r4_paper_lifecycle"]["position_id"]
        == "position-1"
    )


def test_sync_copies_r4_lifecycle_view():
    view = lifecycle_view()

    envelope = DashboardPublicationEnvelopeV1(
        publication_id="publication-1",
        publication_sequence=1,
        published_at=NOW,
        source_updated_at=NOW,
        publication_status="NO_ACTION",
        freshness_status="FRESH",
        r4_paper_lifecycle=view,
    )

    snapshot = DashboardPublicationSnapshotV1(
        latest_envelope=envelope,
        last_successful_publication_at=NOW,
        last_attempted_publication_at=NOW,
        last_attempt_status="PUBLISHED",
        last_attempt_error=None,
        publication_count=1,
        failed_attempt_count=0,
    )

    state = {}

    assert synchronize_dashboard_publication(
        state,
        snapshot,
    ) is True

    assert (
        state[R4_PAPER_LIFECYCLE_VIEW_STATE_KEY]
        is view
    )


def test_runtime_producer_publishes_provider_lifecycle_view():
    view = lifecycle_view()
    store = DashboardPublicationStore()

    producer = DashboardRuntimePublicationProducer(
        store=store,
        clock=lambda: NOW,
        publication_id_factory=(
            lambda cycle_input, cycle_result, sequence: (
                f"publication-{sequence}"
            )
        ),
        lifecycle_view_provider=(
            lambda cycle_input, cycle_result, source: view
        ),
    )

    cycle_input = object.__new__(
        PaperOrchestrationCycleInputV1
    )

    for name, value in {
        "trade_opportunity": None,
        "integrated_trade_plan_result": None,
        "p7_persistence_snapshot": None,
    }.items():
        object.__setattr__(
            cycle_input,
            name,
            value,
        )

    cycle_result = object.__new__(
        PaperOrchestrationCycleResultV1
    )

    for name, value in {
        "cycle_result_id": "cycle-result-1",
        "cycle_id": "cycle-1",
        "cycle_idempotency_key": "cycle-key-1",
        "cycle_input_semantic_hash": "semantic-hash-1",
        "cycle_status": "COMPLETED_NO_ACTION",
        "terminal_stage": "P7_LIFECYCLE",
        "started_at": NOW,
        "completed_at": NOW,
        "stage_results": (),
        "paper_actions": (),
        "blockers": (),
        "warnings": (),
        "errors": (),
        "metadata": {
            "execution_mode": "PAPER",
            "broker_order_submission": False,
        },
    }.items():
        object.__setattr__(
            cycle_result,
            name,
            value,
        )

    snapshot = producer.publish_cycle(
        cycle_input=cycle_input,
        cycle_result=cycle_result,
        source="MONITORING",
    )

    assert snapshot.latest_envelope is not None
    assert (
        snapshot.latest_envelope.r4_paper_lifecycle
        is view
    )