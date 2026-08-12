"""Regression coverage for non-authoritative Task 9 dashboard publication."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from services.certification.task9_live_paper_certification_launcher import (
    Task9LivePaperCycleResultStore,
    Task9LivePaperCertificationLauncher,
)
from services.certification.task9_live_paper_certification_runner import (
    Task9LivePaperCycleResultV1,
)
from services.dashboard_publication import (
    DashboardPublicationEnvelopeV1,
    DashboardPublicationSnapshotV1,
)
from services.dashboard_publication.dashboard_publication_persistent_store import (
    DashboardPublicationPersistentStore,
)
from services.dashboard_read_models import DashboardApplicationViewV1


NOW = datetime(2026, 8, 10, 13, 5, tzinfo=timezone.utc)


def _snapshot():
    view = DashboardApplicationViewV1("legacy-view", NOW, "READ_ONLY")
    envelope = DashboardPublicationEnvelopeV1(
        publication_id="legacy-publication",
        publication_sequence=1,
        published_at=NOW,
        source_updated_at=NOW,
        publication_status="NO_ACTION",
        freshness_status="UNKNOWN",
        application_view=view,
    )
    return DashboardPublicationSnapshotV1(
        latest_envelope=envelope,
        last_successful_publication_at=NOW,
        last_attempted_publication_at=NOW,
        last_attempt_status="PUBLISHED",
        last_attempt_error=None,
        publication_count=1,
        failed_attempt_count=0,
    )


def _legacy_document(tmp_path):
    store = DashboardPublicationPersistentStore(tmp_path)
    snapshot = _snapshot()
    store.persist(snapshot)
    document = json.loads(store.file_path.read_text(encoding="utf-8"))
    application_view = document["snapshot"]["latest_envelope"]["application_view"]
    application_view.pop("external_provider_blocker")
    return store, document


def test_old_official_style_application_view_recovers_without_blocker(tmp_path):
    store, document = _legacy_document(tmp_path)
    store.file_path.write_text(json.dumps(document), encoding="utf-8")

    recovered = DashboardPublicationPersistentStore(tmp_path).recover()

    assert recovered.latest_envelope.application_view.external_provider_blocker is None


def test_old_view_missing_required_field_and_unknown_field_fail_closed(tmp_path):
    store, document = _legacy_document(tmp_path)
    application_view = document["snapshot"]["latest_envelope"]["application_view"]
    application_view.pop("view_id")
    store.file_path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError):
        DashboardPublicationPersistentStore(tmp_path).recover()

    store.file_path.unlink()
    _, document = _legacy_document(tmp_path)
    document["snapshot"]["latest_envelope"]["application_view"]["unknown"] = True
    store.file_path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError):
        DashboardPublicationPersistentStore(tmp_path).recover()


def test_current_dashboard_snapshot_round_trips_exactly(tmp_path):
    source = _snapshot()
    DashboardPublicationPersistentStore(tmp_path).persist(source)
    assert DashboardPublicationPersistentStore(tmp_path).recover() == source


def test_lazy_dashboard_publication_succeeds_after_receipt(tmp_path):
    launcher = Task9LivePaperCertificationLauncher(
        persistence_root=tmp_path,
        official_run_id="run",
        clock=lambda: NOW,
        sleep=lambda _: None,
    )
    result = Task9LivePaperCycleResultV1(
        cycle_id="task9:run:cycle",
        started_at=NOW,
        completed_at=NOW,
        market_results=(),
    )
    Task9LivePaperCycleResultStore(tmp_path).save(result)

    launcher._publish_after_authoritative_persist(result)

    recovered = DashboardPublicationPersistentStore(tmp_path).recover()
    assert recovered.latest_envelope.publication_sequence == 1
    assert list((tmp_path / "task9-cycle-results").glob("*.json"))


@pytest.mark.parametrize("failure", ("constructor", "publish"))
def test_dashboard_failure_cannot_undo_authoritative_cycle_receipt(
    tmp_path, monkeypatch, caplog, failure
):
    launcher = Task9LivePaperCertificationLauncher(
        persistence_root=tmp_path,
        official_run_id="run",
        clock=lambda: NOW,
        sleep=lambda _: None,
    )
    result = Task9LivePaperCycleResultV1(
        cycle_id="task9:run:cycle",
        started_at=NOW,
        completed_at=NOW,
        market_results=(),
    )
    Task9LivePaperCycleResultStore(tmp_path).save(result)

    if failure == "constructor":
        monkeypatch.setattr(
            "services.certification.task9_live_paper_certification_launcher."
            "DashboardPublicationPersistentStore",
            lambda _: (_ for _ in ()).throw(RuntimeError()),
        )
    else:
        monkeypatch.setattr(
            "services.certification.task9_live_paper_certification_launcher."
            "Task9DashboardPublicationPublisher.publish",
            lambda *_: (_ for _ in ()).throw(RuntimeError()),
        )

    launcher._publish_after_authoritative_persist(result)

    assert list((tmp_path / "task9-cycle-results").glob("*.json"))
    assert "TASK9_DASHBOARD_PUBLICATION_FAILED" in caplog.text
    assert result.broker_order_submission is False
    assert result.live_execution_eligible is False
