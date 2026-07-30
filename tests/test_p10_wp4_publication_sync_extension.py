from datetime import datetime, timezone

from dashboard.dashboard_publication_sync import (
    OPTION_INTELLIGENCE_STATE_KEY,
    RUNTIME_OPERATIONS_STATE_KEY,
    synchronize_dashboard_publication,
)
from services.dashboard_publication import (
    DashboardPublicationEnvelopeV1,
    DashboardPublicationSnapshotV1,
)
from services.dashboard_read_models.dashboard_option_intelligence_view_v1 import (
    DashboardOptionIntelligenceViewV1,
)
from services.dashboard_read_models.dashboard_runtime_operations_view_v1 import (
    DashboardRuntimeOperationsViewV1,
)


NOW = datetime(2026, 7, 30, 15, 30, tzinfo=timezone.utc)


def test_sync_copies_option_and_runtime_views():
    option = DashboardOptionIntelligenceViewV1(
        source_id="option-1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        status="READY",
        source_updated_at=NOW,
    )
    runtime = DashboardRuntimeOperationsViewV1(
        source_id="cycle-1",
        runtime_status="COMPLETED",
        source_updated_at=NOW,
    )
    envelope = DashboardPublicationEnvelopeV1(
        publication_id="publication-1",
        publication_sequence=1,
        published_at=NOW,
        source_updated_at=NOW,
        publication_status="NO_ACTION",
        freshness_status="FRESH",
        option_intelligence=option,
        runtime_operations=runtime,
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

    assert synchronize_dashboard_publication(state, snapshot) is True
    assert state[OPTION_INTELLIGENCE_STATE_KEY] is option
    assert state[RUNTIME_OPERATIONS_STATE_KEY] is runtime
