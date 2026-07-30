from datetime import datetime, timezone

import pytest

from services.dashboard_publication import (
    DashboardPublicationEnvelopeV1,
    DashboardPublicationStore,
    clear_dashboard_publication_store_registration,
    get_registered_dashboard_publication_snapshot,
    register_dashboard_publication_store,
)


NOW = datetime(2026, 7, 30, 16, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def clear_registry():
    clear_dashboard_publication_store_registration()
    yield
    clear_dashboard_publication_store_registration()


def test_registry_starts_unconfigured():
    assert get_registered_dashboard_publication_snapshot() is None


def test_registry_exposes_store_snapshot_only():
    store = DashboardPublicationStore()
    register_dashboard_publication_store(store)

    snapshot = get_registered_dashboard_publication_snapshot()

    assert snapshot is not None
    assert snapshot.latest_envelope is None


def test_registry_reads_latest_publication():
    store = DashboardPublicationStore()
    register_dashboard_publication_store(store)
    envelope = DashboardPublicationEnvelopeV1(
        publication_id="publication-1",
        publication_sequence=1,
        published_at=NOW,
        source_updated_at=NOW,
        publication_status="BLOCKED",
        freshness_status="FRESH",
        blockers=("BLOCKED",),
    )
    store.publish(envelope, attempted_at=NOW)

    snapshot = get_registered_dashboard_publication_snapshot()

    assert snapshot.latest_envelope is envelope


def test_registry_rejects_untyped_store():
    with pytest.raises(TypeError, match="exact"):
        register_dashboard_publication_store(object())
