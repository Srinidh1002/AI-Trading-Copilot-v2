"""Task 9.97 certified progress -> dashboard publication bridge."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from services.certification.task9_live_paper_certification_runner import (
    Task9LivePaperCycleResultV1,
)
from services.contracts.task9_live_paper_certification_progress_v1 import (
    Task9LivePaperCertificationProgressV1,
    Task9MarketProgressV1,
)
from services.dashboard_publication.dashboard_publication_persistent_store import (
    DashboardPublicationPersistentStore,
)
from services.dashboard_publication.dashboard_publication_store import (
    DashboardPublicationStore,
)
from services.dashboard_publication.task9_dashboard_publication_publisher import (
    Task9DashboardPublicationPublisher,
)
NOW = datetime(
    2026,
    8,
    18,
    5,
    0,
    tzinfo=timezone.utc,
)


def _cycle_result(
    *,
    cycle_id="task997-cycle",
):
    value = object.__new__(
        Task9LivePaperCycleResultV1
    )
    object.__setattr__(
        value,
        "cycle_id",
        cycle_id,
    )
    object.__setattr__(
        value,
        "completed_at",
        NOW,
    )
    return value


def _progress():
    return Task9LivePaperCertificationProgressV1(
        nifty=Task9MarketProgressV1(
            market="NIFTY",
            target_trade_count=100,
            completed_live_paper_trades=12,
            pending_entered_trades=2,
            no_trade_completed=3,
            no_trade_passed=2,
            no_trade_failed=1,
            wait_completed=4,
            wait_passed=3,
            wait_failed=1,
        ),
        sensex=Task9MarketProgressV1(
            market="SENSEX",
            target_trade_count=100,
            completed_live_paper_trades=9,
            pending_entered_trades=1,
            no_trade_completed=2,
            no_trade_passed=1,
            no_trade_failed=1,
            wait_completed=5,
            wait_passed=4,
            wait_failed=1,
        ),
        replay_excluded=7,
        duplicate_excluded=2,
        invalid_excluded=4,
        unresolved=3,
        certification_complete=False,
    )


def _write_progress(
    root,
    progress=None,
):
    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        root
        / "task9-live-paper-certification-progress.json"
    ).write_text(
        json.dumps(
            (
                progress
                or _progress()
            ).to_dict()
        ),
        encoding="utf-8",
    )


def _publisher(root):
    persistent_store = (
        DashboardPublicationPersistentStore(
            root
        )
    )

    store = DashboardPublicationStore(
        persistent_store=persistent_store
    )

    publisher = (
        Task9DashboardPublicationPublisher(
            store=store,
            persistence_root=root,
        )
    )

    return publisher, store


def test_publishes_exact_persisted_certification_progress(
    tmp_path,
):
    expected = _progress()
    _write_progress(
        tmp_path,
        expected,
    )

    publisher, store = _publisher(
        tmp_path
    )

    result = _cycle_result()

    publisher.publish(result)

    snapshot = store.get_snapshot()

    assert (
        snapshot.latest_envelope
        is not None
    )

    view = (
        snapshot
        .latest_envelope
        .application_view
    )

    assert view is not None

    assert (
        view.task9_certification_progress
        == expected
    )

    assert (
        view
        .task9_certification_progress
        .nifty
        .wait_completed,
        view
        .task9_certification_progress
        .nifty
        .wait_passed,
        view
        .task9_certification_progress
        .nifty
        .wait_failed,
    ) == (
        4,
        3,
        1,
    )

    assert (
        view
        .task9_certification_progress
        .sensex
        .no_trade_completed
        == 2
    )

    assert (
        view.execution_mode
        == "PAPER"
    )

    assert (
        view.live_execution_eligible
        is False
    )

    assert (
        view.broker_order_submission
        is False
    )

    assert view.read_only is True


def test_missing_progress_authority_fails_closed(
    tmp_path,
):
    publisher, store = _publisher(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_CERTIFICATION_PROGRESS_AUTHORITY_UNAVAILABLE"
        ),
    ):
        publisher.publish(
            _cycle_result()
        )

    assert (
        store
        .get_snapshot()
        .latest_envelope
        is None
    )


def test_malformed_progress_authority_fails_closed(
    tmp_path,
):
    (
        tmp_path
        / "task9-live-paper-certification-progress.json"
    ).write_text(
        "{}",
        encoding="utf-8",
    )

    publisher, store = _publisher(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_CERTIFICATION_PROGRESS_AUTHORITY_UNAVAILABLE"
        ),
    ):
        publisher.publish(
            _cycle_result()
        )

    assert (
        store
        .get_snapshot()
        .latest_envelope
        is None
    )


def test_failed_new_publication_preserves_last_known_good(
    tmp_path,
):
    _write_progress(
        tmp_path
    )

    publisher, store = _publisher(
        tmp_path
    )

    first = _cycle_result()

    publisher.publish(first)

    before = (
        store
        .get_snapshot()
        .latest_envelope
    )

    assert before is not None

    (
        tmp_path
        / "task9-live-paper-certification-progress.json"
    ).write_text(
        "{}",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_CERTIFICATION_PROGRESS_AUTHORITY_UNAVAILABLE"
        ),
    ):
        publisher.publish(
            _cycle_result(
                cycle_id=(
                    f"{first.cycle_id}-next"
                ),
            )
        )

    after = (
        store
        .get_snapshot()
        .latest_envelope
    )

    assert after == before


def test_publisher_source_has_no_progress_recomputation_or_provider_broker_dependency():
    import inspect

    import services.dashboard_publication.task9_dashboard_publication_publisher as module

    source = inspect.getsource(
        module
    ).lower()

    for forbidden in (
        "build_task9_live_paper_certification_progress",
        "evaluate_task9_live_paper_trade_counting",
        "angel",
        "requests.",
        "httpx.",
        "socket.",
        "place_order",
        "submit_order",
    ):
        assert forbidden not in source
