"""Task 9 certified-progress adapter for canonical dashboard publication."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from services.certification.task9_live_paper_certification_runner import (
    Task9LivePaperCycleResultV1,
)
from services.dashboard_read_models.dashboard_application_view_v1 import (
    DashboardApplicationViewV1,
)
from services.dashboard_read_models.task9_durable_authority_recovery import (
    _read_current_task9_progress,
)

from .dashboard_publication_envelope_v1 import (
    DashboardPublicationEnvelopeV1,
)
from .dashboard_publication_store import (
    DashboardPublicationStore,
)


class Task9DashboardPublicationPublisher:
    """Publish only already-persisted certified Task 9 progress."""

    def __init__(
        self,
        *,
        store: DashboardPublicationStore,
        persistence_root,
    ) -> None:
        if type(store) is not DashboardPublicationStore:
            raise TypeError("store")

        self.store = store
        self.persistence_root = Path(
            persistence_root
        )

    def _publish_progress(
        self,
        *,
        source_id: str,
        published_at: datetime,
    ) -> None:
        if (
            type(source_id) is not str
            or not source_id.strip()
        ):
            raise ValueError("source_id")

        source_id = source_id.strip()

        if (
            not isinstance(published_at, datetime)
            or published_at.tzinfo is None
            or published_at.utcoffset() is None
        ):
            raise ValueError("published_at")

        progress = _read_current_task9_progress(
            self.persistence_root
        )

        if progress is None:
            raise ValueError(
                "TASK9_CERTIFICATION_PROGRESS_AUTHORITY_UNAVAILABLE"
            )

        latest = (
            self.store
            .get_snapshot()
            .latest_envelope
        )

        sequence = (
            1
            if latest is None
            else latest.publication_sequence + 1
        )

        application_view = (
            DashboardApplicationViewV1(
                view_id=(
                    "task9-dashboard:"
                    f"{source_id}"
                ),
                generated_at=published_at,
                market_session_state=(
                    "PUBLISHED_RUNTIME_STATE"
                ),
                task9_certification_progress=(
                    progress
                ),
                warnings=(
                    "Task 9 certification progress "
                    "is projected from the persisted "
                    "certification authority.",
                ),
            )
        )

        envelope = (
            DashboardPublicationEnvelopeV1(
                publication_id=(
                    "task9-dashboard:"
                    f"{source_id}:"
                    f"{sequence}"
                ),
                publication_sequence=sequence,
                published_at=published_at,
                source_updated_at=published_at,
                publication_status="NO_ACTION",
                freshness_status="FRESH",
                application_view=application_view,
                warnings=application_view.warnings,
            )
        )

        self.store.publish(
            envelope,
            attempted_at=published_at,
        )

    def publish(
        self,
        result: Task9LivePaperCycleResultV1,
    ) -> None:
        if type(result) is not Task9LivePaperCycleResultV1:
            raise TypeError("result")

        self._publish_progress(
            source_id=result.cycle_id,
            published_at=result.completed_at,
        )

    def publish_persisted_progress(
        self,
        *,
        source_id: str,
        published_at: datetime,
    ) -> None:
        """Publish only already-persisted Task 9 progress.

        This boundary is used after provider-free lifecycle/close-drain
        persistence.  It never creates or pretends to create a trading cycle.
        """

        self._publish_progress(
            source_id=source_id,
            published_at=published_at,
        )
