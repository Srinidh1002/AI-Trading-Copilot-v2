from datetime import datetime, timezone

from services.dashboard_publication.dashboard_publication_store import (
    DashboardPublicationStore,
)
from services.dashboard_publication.dashboard_runtime_publication_producer import (
    DashboardRuntimePublicationProducer,
)
from services.paper_orchestration.certified_dashboard_composition import (
    CertifiedDashboardPublicationCompositionV1,
    build_certified_dashboard_publication,
)


NOW = datetime(2026, 1, 8, 10, 0, tzinfo=timezone.utc)


def test_builds_exact_dashboard_store_and_producer():
    result = build_certified_dashboard_publication(clock=lambda: NOW)

    assert type(result) is CertifiedDashboardPublicationCompositionV1
    assert type(result.store) is DashboardPublicationStore
    assert type(result.producer) is DashboardRuntimePublicationProducer
    assert result.producer.store is result.store
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False
