"""Task 9 daily finalization archives only closed, prior sessions."""
from __future__ import annotations

from datetime import timedelta

import pytest

from services.reporting.paper_certification_report_archive import (
    PaperCertificationReportArchive,
)
from services.certification.task9_certification_publication import _content_hash
from services.certification.task9_close_drain_state_store import Task9CloseDrainStateStore
from services.contracts.task9_close_drain_state_v1 import (
    Task9CloseDrainItemKind,
    Task9CloseDrainItemStatus,
    Task9CloseDrainItemV1,
    Task9CloseDrainStateV1,
    Task9CloseDrainStatus,
)
from tests.test_task927_failed_child_publication import _authority
from tests.test_task916_production_child_evidence_authority import _runtime


def _save_close_drain(
    authority,
    *,
    session_date,
    evaluated_at,
    status=Task9CloseDrainStatus.COMPLETE,
):
    if status is Task9CloseDrainStatus.COMPLETE:
        items = ()
        reasons = ()
    else:
        items = (
            Task9CloseDrainItemV1(
                prediction_id="task928-pending",
                market="NIFTY",
                kind=Task9CloseDrainItemKind.ABSTENTION,
                status=Task9CloseDrainItemStatus.PENDING,
                reason_codes=("ABSTENTION_VALIDITY_PENDING",),
            ),
        )
        reasons = ("ABSTENTION_VALIDITY_PENDING",)

    state = Task9CloseDrainStateV1(
        official_run_id=authority.official_run_id,
        market_date=session_date,
        evaluated_at=evaluated_at,
        status=status,
        session_phases=(
            ("NIFTY", "CLOSED"),
            ("SENSEX", "CLOSED"),
        ),
        items=items,
        reason_codes=reasons,
    )

    return Task9CloseDrainStateStore(
        authority.root
    ).save(state)


def _setup(tmp_path, *, seal_close_drain=True):
    runtime = _runtime(tmp_path, nifty_action="WAIT", sensex_action="NO_TRADE")
    prediction = runtime["predictions"][0]
    authority = _authority(tmp_path, runtime, "task9-daily-finalization", prediction)
    session_date = prediction.completed_at.date()
    authority.refresh(session_date=session_date, evaluated_at=prediction.completed_at)

    if seal_close_drain:
        _save_close_drain(
            authority,
            session_date=session_date,
            evaluated_at=prediction.completed_at + timedelta(days=1),
        )

    return authority, prediction, session_date


def test_closed_prior_session_archives_then_indexes_idempotently(tmp_path):
    authority, prediction, session_date = _setup(tmp_path)
    finalized_at = prediction.completed_at + timedelta(days=1)

    first = authority.finalize_session(session_date=session_date, evaluated_at=finalized_at, session_closed=True)
    record = authority.index.all_records()[0]
    archive = authority.archive_root / record["archive_path"]

    assert archive.is_file()
    assert record["report_id"] == authority._finalized_report_id(session_date)
    assert ":" not in record["report_id"]
    assert ":" not in record["archive_path"]
    assert record["archive_path"] == authority._archive_path(session_date).as_posix()
    assert authority.index.count() == 1
    archive_before_retry = archive.read_bytes()
    second = authority.finalize_session(session_date=session_date, evaluated_at=finalized_at + timedelta(minutes=1), session_closed=True)
    assert authority.index.count() == 1
    assert archive.read_bytes() == archive_before_retry
    assert second.to_dict() == first.to_dict()


def test_open_current_session_cannot_finalize(tmp_path):
    authority, prediction, session_date = _setup(tmp_path)
    with pytest.raises(ValueError, match="TASK9_SESSION_NOT_CLOSED"):
        authority.finalize_session(session_date=session_date, evaluated_at=prediction.completed_at, session_closed=True)


def test_archive_written_before_index_is_recovered_by_finalization(tmp_path):
    authority, prediction, session_date = _setup(tmp_path)
    finalized_at = prediction.completed_at + timedelta(days=1)
    report = authority._build_finalized_report(session_date=session_date, evaluated_at=finalized_at)
    PaperCertificationReportArchive(authority.archive_root).save(report)

    authority.finalize_session(session_date=session_date, evaluated_at=finalized_at, session_closed=True)
    assert authority.index.count() == 1
    assert authority.index.all_records()[0]["semantic_hash"] == report.semantic_hash


def test_draft_identity_remains_mutable_while_finalized_identity_is_safe(tmp_path):
    authority, prediction, session_date = _setup(tmp_path)
    draft = authority._build_report(session_date=session_date, evaluated_at=prediction.completed_at)
    finalized = authority._build_finalized_report(session_date=session_date, evaluated_at=prediction.completed_at)

    assert draft.report_id == f"task9-draft:task9-daily-finalization:{session_date.isoformat()}"
    assert finalized.report_id == f"task9-daily-task9-daily-finalization-{session_date.isoformat()}"
    assert _content_hash(draft.to_dict()) == _content_hash(finalized.to_dict())


def test_refresh_rollover_finalizes_only_prior_draft_and_never_double_counts(tmp_path):
    authority, prediction, session_date = _setup(tmp_path)
    next_session = session_date + timedelta(days=1)
    next_at = prediction.completed_at + timedelta(days=1)

    authority.refresh(session_date=next_session, evaluated_at=next_at)
    assert authority.index.count() == 1
    assert authority.index.all_records()[0]["session_date"] == session_date.isoformat()
    assert (authority.root / "task9-live-paper-certification-progress.json").is_file()
    first = (authority.root / "task9-live-paper-certification-progress.json").read_bytes()
    authority.refresh(session_date=next_session, evaluated_at=next_at + timedelta(minutes=1))
    assert authority.index.count() == 1
    assert (authority.root / "task9-live-paper-certification-progress.json").read_bytes() == first


def test_legacy_session_closed_boolean_cannot_bypass_missing_close_drain(tmp_path):
    authority, prediction, session_date = _setup(
        tmp_path,
        seal_close_drain=False,
    )
    finalized_at = prediction.completed_at + timedelta(days=1)

    with pytest.raises(
        ValueError,
        match="TASK9_CLOSE_DRAIN_STATE_MISSING",
    ):
        authority.finalize_session(
            session_date=session_date,
            evaluated_at=finalized_at,
            session_closed=True,
        )

    assert authority.index.count() == 0


def test_pending_close_drain_keeps_prior_draft_unfinalized_on_rollover(tmp_path):
    authority, prediction, session_date = _setup(
        tmp_path,
        seal_close_drain=False,
    )
    next_session = session_date + timedelta(days=1)
    next_at = prediction.completed_at + timedelta(days=1)

    _save_close_drain(
        authority,
        session_date=session_date,
        evaluated_at=next_at,
        status=Task9CloseDrainStatus.PENDING,
    )

    finalized = authority.rollover(
        session_date=next_session,
        evaluated_at=next_at,
    )

    assert finalized == ()
    assert authority.index.count() == 0
    assert authority._draft_path(session_date).is_file()


def test_blocked_close_drain_fails_visible_and_does_not_archive(tmp_path):
    authority, prediction, session_date = _setup(
        tmp_path,
        seal_close_drain=False,
    )
    next_session = session_date + timedelta(days=1)
    next_at = prediction.completed_at + timedelta(days=1)

    blocked = Task9CloseDrainStateV1(
        official_run_id=authority.official_run_id,
        market_date=session_date,
        evaluated_at=next_at,
        status=Task9CloseDrainStatus.BLOCKED,
        session_phases=(
            ("NIFTY", "CLOSED"),
            ("SENSEX", "CLOSED"),
        ),
        items=(
            Task9CloseDrainItemV1(
                prediction_id="task928-blocked",
                market="NIFTY",
                kind=Task9CloseDrainItemKind.PAPER_TRADE,
                status=Task9CloseDrainItemStatus.BLOCKED,
                reason_codes=("BINDING_IDENTITY_MISMATCH",),
            ),
        ),
        reason_codes=("BINDING_IDENTITY_MISMATCH",),
    )
    Task9CloseDrainStateStore(
        authority.root
    ).save(blocked)

    with pytest.raises(
        ValueError,
        match="TASK9_CLOSE_DRAIN_BLOCKED",
    ):
        authority.rollover(
            session_date=next_session,
            evaluated_at=next_at,
        )

    assert authority.index.count() == 0
    assert authority._draft_path(session_date).is_file()
