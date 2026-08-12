"""Focused cross-process persistence coverage for Task 9 dashboard publication."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from dashboard.dashboard_publication_sync import (
    PUBLICATION_SEQUENCE_STATE_KEY,
    synchronize_registered_dashboard_publication,
)
from services.dashboard_publication import (
    DashboardPublicationEnvelopeV1,
    DashboardPublicationSnapshotV1,
)
from services.dashboard_publication.dashboard_publication_persistent_store import (
    DashboardPublicationPersistentStore,
)
from services.dashboard_read_models import DashboardApplicationViewV1
from services.dashboard_read_models.task9_dashboard_shell import (
    build_task9_dashboard_shell_view,
)


NOW = datetime(2026, 8, 10, 9, 15, tzinfo=timezone.utc)


def _snapshot(sequence=1, view=None):
    view = view or DashboardApplicationViewV1(
        view_id=f"view-{sequence}", generated_at=NOW,
        market_session_state="NOT_YET_PUBLISHED",
    )
    envelope = DashboardPublicationEnvelopeV1(
        publication_id=f"publication-{sequence}", publication_sequence=sequence,
        published_at=NOW, source_updated_at=NOW,
        publication_status="NO_ACTION", freshness_status="UNKNOWN",
        application_view=view,
    )
    return DashboardPublicationSnapshotV1(
        latest_envelope=envelope, last_successful_publication_at=NOW,
        last_attempted_publication_at=NOW, last_attempt_status="PUBLISHED",
        last_attempt_error=None, publication_count=sequence,
        failed_attempt_count=0,
    )


def test_persistent_snapshot_round_trip_preserves_exact_application_view(tmp_path):
    store = DashboardPublicationPersistentStore(tmp_path)
    source = _snapshot(view=DashboardApplicationViewV1(
        view_id="exact", generated_at=NOW, market_session_state="CLOSED",
        blockers=("NO_PUBLICATION",), warnings=("preserved",),
    ))

    store.persist(source)
    recovered = DashboardPublicationPersistentStore(tmp_path).recover()

    assert recovered == source
    assert recovered.latest_envelope.application_view == source.latest_envelope.application_view


def test_missing_file_is_safe_and_corrupt_file_fails_closed(tmp_path):
    store = DashboardPublicationPersistentStore(tmp_path)
    assert store.recover() is None
    (tmp_path / "dashboard-publication.json").write_text("{bad", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid durable"):
        store.recover()


def test_persistent_store_rejects_sequence_rollback_and_conflict_is_idempotent(tmp_path):
    store = DashboardPublicationPersistentStore(tmp_path)
    first = _snapshot(2)
    assert store.persist(first) is first
    assert store.persist(first) is first
    with pytest.raises(ValueError, match="move backwards"):
        store.persist(_snapshot(1))
    with pytest.raises(ValueError, match="different content"):
        store.persist(_snapshot(2, DashboardApplicationViewV1("other", NOW, "CLOSED")))


def test_streamlit_disk_recovery_prefers_newer_snapshot_and_preserves_last_good(tmp_path):
    durable = DashboardPublicationPersistentStore(tmp_path)
    durable.persist(_snapshot(2))
    state = {PUBLICATION_SEQUENCE_STATE_KEY: 1}

    assert synchronize_registered_dashboard_publication(
        state, persistence_root=str(tmp_path)
    ) is True
    assert state[PUBLICATION_SEQUENCE_STATE_KEY] == 2

    (tmp_path / "dashboard-publication.json").write_text("[]", encoding="utf-8")
    assert synchronize_registered_dashboard_publication(
        state, persistence_root=str(tmp_path)
    ) is False
    assert state[PUBLICATION_SEQUENCE_STATE_KEY] == 2


def test_task9_empty_shell_has_all_navigation_without_runtime_claims():
    view = build_task9_dashboard_shell_view()
    source = Path("dashboard/dashboard_navigation.py").read_text(encoding="utf-8")

    assert view.nifty_market is None and view.sensex_market is None
    assert view.task9_certification_progress is None
    for page in ("🎯 Trade Now", "📊 Markets", "💼 Trades & P&L", "🧪 Certification", "🧮 Manual Planner", "⚙️ System Health"):
        assert page in source


def test_dashboard_bridge_has_no_provider_broker_or_progress_mutation_dependency():
    source = "\n".join(
        Path(name).read_text(encoding="utf-8")
        for name in (
            "dashboard/dashboard_publication_sync.py",
            "services/dashboard_publication/dashboard_publication_persistent_store.py",
            "services/dashboard_read_models/task9_dashboard_shell.py",
        )
    ).lower()
    for forbidden in ("angel", "provider", "submit_order", "services.execution", "increment_task9", "sqlite3"):
        assert forbidden not in source
