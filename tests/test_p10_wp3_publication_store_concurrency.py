from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from services.dashboard_publication import (
    DashboardPublicationEnvelopeV1,
    DashboardPublicationStore,
)


NOW = datetime(2026, 7, 30, 13, 30, tzinfo=timezone.utc)


def blocked(sequence):
    return DashboardPublicationEnvelopeV1(
        publication_id=f"publication-{sequence}",
        publication_sequence=sequence,
        published_at=NOW + timedelta(seconds=sequence),
        source_updated_at=NOW,
        publication_status="BLOCKED",
        freshness_status="FRESH",
        blockers=(f"BLOCKED-{sequence}",),
    )


def test_concurrent_duplicate_publications_remain_coherent():
    store = DashboardPublicationStore()
    value = blocked(1)
    attempted_at = NOW + timedelta(seconds=100)

    def publish_duplicate(_):
        return store.publish(
            value,
            attempted_at=attempted_at,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        snapshots = tuple(executor.map(publish_duplicate, range(20)))

    snapshot = store.get_snapshot()

    assert snapshot.latest_envelope is value
    assert snapshot.latest_envelope.publication_sequence == 1
    assert snapshot.publication_count == 1
    assert snapshot.failed_attempt_count == 0

    statuses = tuple(item.last_attempt_status for item in snapshots)
    assert statuses.count("PUBLISHED") == 1
    assert statuses.count("DUPLICATE_NO_CHANGE") == 19


def test_concurrent_reads_during_ordered_publication_are_coherent():
    store = DashboardPublicationStore()

    def read_snapshot(_):
        return store.get_snapshot()

    for sequence in range(1, 21):
        store.publish(
            blocked(sequence),
            attempted_at=NOW + timedelta(seconds=sequence + 100),
        )

        with ThreadPoolExecutor(max_workers=8) as executor:
            snapshots = tuple(executor.map(read_snapshot, range(20)))

        assert all(
            item.latest_envelope is not None
            and item.latest_envelope.publication_sequence == sequence
            and item.publication_count == sequence
            for item in snapshots
        )

    final_snapshot = store.get_snapshot()

    assert final_snapshot.latest_envelope.publication_sequence == 20
    assert final_snapshot.publication_count == 20


def test_concurrent_failures_are_counted_without_clearing_publication():
    store = DashboardPublicationStore()
    value = blocked(1)
    store.publish(
        value,
        attempted_at=NOW + timedelta(seconds=2),
    )

    attempted_at = NOW + timedelta(seconds=100)

    def fail(index):
        return store.record_failure(
            attempted_at=attempted_at,
            error=f"failure-{index}",
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        tuple(executor.map(fail, range(1, 21)))

    snapshot = store.get_snapshot()

    assert snapshot.latest_envelope is value
    assert snapshot.publication_count == 1
    assert snapshot.failed_attempt_count == 20
    assert snapshot.last_attempt_status == "FAILED_ATTEMPT_PRESERVED"