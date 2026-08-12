"""Task 9 runner-result adapter for the canonical dashboard publication store."""
from __future__ import annotations

from services.certification.task9_live_paper_certification_runner import (
    Task9LivePaperCycleResultV1,
)
from services.dashboard_read_models.dashboard_application_view_v1 import (
    DashboardApplicationViewV1,
)

from .dashboard_publication_envelope_v1 import DashboardPublicationEnvelopeV1
from .dashboard_publication_store import DashboardPublicationStore


class Task9DashboardPublicationPublisher:
    """Publish runner receipts without projecting market data or progress."""

    def __init__(self, *, store: DashboardPublicationStore) -> None:
        if type(store) is not DashboardPublicationStore:
            raise TypeError("store")
        self.store = store

    def publish(self, result: Task9LivePaperCycleResultV1) -> None:
        if type(result) is not Task9LivePaperCycleResultV1:
            raise TypeError("result")
        latest = self.store.get_snapshot().latest_envelope
        sequence = 1 if latest is None else latest.publication_sequence + 1
        application_view = DashboardApplicationViewV1(
            view_id=f"task9-dashboard:{result.cycle_id}",
            generated_at=result.completed_at,
            market_session_state="PUBLISHED_RUNTIME_STATE",
            blockers=("LIVE_DETAIL_NOT_PUBLISHED_BY_RUNNER",),
            warnings=(
                "This read-only publication contains no independently acquired market data or Task 9 progress.",
            ),
        )
        envelope = DashboardPublicationEnvelopeV1(
            publication_id=f"task9-dashboard:{result.cycle_id}:{sequence}",
            publication_sequence=sequence,
            published_at=result.completed_at,
            source_updated_at=result.completed_at,
            publication_status="NO_ACTION",
            freshness_status="UNKNOWN",
            application_view=application_view,
            warnings=application_view.warnings,
        )
        self.store.publish(envelope, attempted_at=result.completed_at)
