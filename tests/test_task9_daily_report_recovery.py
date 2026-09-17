import json
from pathlib import Path

import pytest

from services.certification.task9_daily_report_index import (
    Task9DailyReportIndex,
)
from services.certification.task9_daily_report_recovery import (
    recover_task9_daily_reports,
)
from services.certification.task9_live_paper_certification_progress_builder import (
    build_task9_live_paper_certification_progress,
    build_task9_live_paper_certification_progress_from_raw,
)
from services.reporting.paper_certification_report_archive import (
    PaperCertificationReportArchive,
)
from tests.r79_reporting_helpers import (
    build_daily,
    clone_daily,
)


RUN_ID = "task9-live-run-1"


def archive_and_index(
    tmp_path: Path,
    *,
    report=None,
):
    report = report or build_daily()

    archive_root = tmp_path / "certification_reports"
    archive = PaperCertificationReportArchive(archive_root)

    saved = archive.save(report)
    assert saved["status"] == "SAVED"

    relative_path = (
        Path("daily")
        / report.session_date.isoformat()
        / f"{report.report_id}.json"
    )

    index = Task9DailyReportIndex(
        official_run_id=RUN_ID,
        file_path=(
            tmp_path
            / "task9_daily_report_index.json"
        ),
    )

    status = index.save(
        report_id=report.report_id,
        session_date=report.session_date.isoformat(),
        semantic_hash=report.semantic_hash,
        archive_path=relative_path.as_posix(),
    )

    assert status == "SAVED"

    return report, archive_root, index, relative_path


def test_index_is_restart_safe_and_idempotent(tmp_path):
    report, _, index, relative_path = archive_and_index(
        tmp_path
    )

    restarted = Task9DailyReportIndex(
        official_run_id=RUN_ID,
        file_path=index.file_path,
    )

    assert restarted.count() == 1

    assert restarted.save(
        report_id=report.report_id,
        session_date=report.session_date.isoformat(),
        semantic_hash=report.semantic_hash,
        archive_path=relative_path.as_posix(),
    ) == "DUPLICATE_SAME_PAYLOAD"

    assert restarted.count() == 1


def test_index_rejects_conflicting_same_session_date(tmp_path):
    report, _, index, relative_path = archive_and_index(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="TASK9_DAILY_REPORT_INDEX_CONFLICT",
    ):
        index.save(
            report_id="different-report",
            session_date=report.session_date.isoformat(),
            semantic_hash="a" * 64,
            archive_path=relative_path.as_posix(),
        )


def test_index_rejects_same_report_id_on_different_date(tmp_path):
    report, _, index, _ = archive_and_index(tmp_path)

    with pytest.raises(
        ValueError,
        match="TASK9_REPORT_ID_ALREADY_INDEXED",
    ):
        index.save(
            report_id=report.report_id,
            session_date="2026-08-06",
            semantic_hash=report.semantic_hash,
            archive_path=(
                "daily/2026-08-06/daily-1.json"
            ),
        )


@pytest.mark.parametrize(
    "archive_path",
    (
        "../escape.json",
        "../../outside.json",
    ),
)
def test_index_rejects_unsafe_archive_path(
    tmp_path,
    archive_path,
):
    index = Task9DailyReportIndex(
        official_run_id=RUN_ID,
        file_path=tmp_path / "index.json",
    )

    with pytest.raises(
        ValueError,
        match="safe relative path",
    ):
        index.save(
            report_id="daily-1",
            session_date="2026-08-05",
            semantic_hash="a" * 64,
            archive_path=archive_path,
        )


def test_restart_recovery_matches_typed_progress(tmp_path):
    report, archive_root, index, _ = archive_and_index(
        tmp_path
    )

    recovered = recover_task9_daily_reports(
        index=index,
        official_run_id=RUN_ID,
        archive_root=archive_root,
    )

    assert len(recovered) == 1
    assert recovered[0] == report.to_dict()

    typed_progress = (
        build_task9_live_paper_certification_progress(
            (report,)
        )
    )
    recovered_progress = (
        build_task9_live_paper_certification_progress_from_raw(
            recovered
        )
    )

    assert (
        recovered_progress.to_dict()
        == typed_progress.to_dict()
    )


def test_restart_detects_archived_report_tampering(tmp_path):
    report, archive_root, index, relative_path = (
        archive_and_index(tmp_path)
    )

    path = archive_root / relative_path
    raw = json.loads(
        path.read_text(encoding="utf-8")
    )

    raw["starting_capital"] += 1.0

    path.write_text(
        json.dumps(
            raw,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="semantic-hash mismatch",
    ):
        recover_task9_daily_reports(
            index=index,
            official_run_id=RUN_ID,
            archive_root=archive_root,
        )


def test_restart_detects_missing_archived_report(tmp_path):
    _, archive_root, index, relative_path = (
        archive_and_index(tmp_path)
    )

    (archive_root / relative_path).unlink()

    with pytest.raises(FileNotFoundError):
        recover_task9_daily_reports(
            index=index,
            official_run_id=RUN_ID,
            archive_root=archive_root,
        )


def test_restart_rejects_report_identity_mismatch(tmp_path):
    _, archive_root, index, relative_path = (
        archive_and_index(tmp_path)
    )

    path = archive_root / relative_path
    raw = json.loads(
        path.read_text(encoding="utf-8")
    )
    raw["report_id"] = "wrong-report"

    path.write_text(
        json.dumps(
            raw,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="report-id mismatch",
    ):
        recover_task9_daily_reports(
            index=index,
            official_run_id=RUN_ID,
            archive_root=archive_root,
        )


def test_recovered_report_remains_paper_only(tmp_path):
    _, archive_root, index, relative_path = (
        archive_and_index(tmp_path)
    )

    path = archive_root / relative_path
    raw = json.loads(
        path.read_text(encoding="utf-8")
    )
    raw["broker_order_submission"] = True

    path.write_text(
        json.dumps(
            raw,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="recovered report safety",
    ):
        recover_task9_daily_reports(
            index=index,
            official_run_id=RUN_ID,
            archive_root=archive_root,
        )


def test_restart_rejects_different_official_run_id(
    tmp_path,
):
    _, _, index, _ = archive_and_index(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="TASK9_OFFICIAL_RUN_ID_MISMATCH",
    ):
        Task9DailyReportIndex(
            official_run_id="different-task9-run",
            file_path=index.file_path,
        )


def test_recovery_rejects_requested_run_mismatch(
    tmp_path,
):
    _, archive_root, index, _ = (
        archive_and_index(tmp_path)
    )

    with pytest.raises(
        ValueError,
        match="TASK9_OFFICIAL_RUN_ID_MISMATCH",
    ):
        recover_task9_daily_reports(
            index=index,
            official_run_id="different-task9-run",
            archive_root=archive_root,
        )


def test_multi_day_restart_recovery_preserves_progress(
    tmp_path,
):
    first = build_daily(
        report_id="task9-day-1",
    )
    second = clone_daily(
        first,
        report_id="task9-day-2",
        day_offset=1,
    )

    archive_root = (
        tmp_path
        / "certification_reports"
    )
    archive = PaperCertificationReportArchive(
        archive_root
    )

    index_path = (
        tmp_path
        / "task9_daily_report_index.json"
    )

    index = Task9DailyReportIndex(
        official_run_id=RUN_ID,
        file_path=index_path,
    )

    for report in (
        first,
        second,
    ):
        saved = archive.save(
            report
        )
        assert (
            saved["status"]
            == "SAVED"
        )

        relative_path = (
            Path("daily")
            / report.session_date.isoformat()
            / f"{report.report_id}.json"
        )

        assert index.save(
            report_id=report.report_id,
            session_date=(
                report.session_date.isoformat()
            ),
            semantic_hash=report.semantic_hash,
            archive_path=(
                relative_path.as_posix()
            ),
        ) == "SAVED"

    restarted = Task9DailyReportIndex(
        official_run_id=RUN_ID,
        file_path=index_path,
    )

    recovered = recover_task9_daily_reports(
        index=restarted,
        official_run_id=RUN_ID,
        archive_root=archive_root,
    )

    assert [
        item["session_date"]
        for item in recovered
    ] == [
        first.session_date.isoformat(),
        second.session_date.isoformat(),
    ]

    progress = (
        build_task9_live_paper_certification_progress_from_raw(
            recovered
        )
    )

    expected = (
        build_task9_live_paper_certification_progress(
            (
                first,
                second,
            )
        )
    )

    assert (
        progress.to_dict()
        == expected.to_dict()
    )


def test_restart_does_not_double_count_same_multi_day_reports(
    tmp_path,
):
    first = build_daily(
        report_id="task9-day-1",
    )

    second = clone_daily(
        first,
        report_id="task9-day-2",
        day_offset=1,
    )

    archive_root = (
        tmp_path
        / "certification_reports"
    )

    archive = PaperCertificationReportArchive(
        archive_root
    )

    index_path = (
        tmp_path
        / "task9_daily_report_index.json"
    )

    index = Task9DailyReportIndex(
        official_run_id=RUN_ID,
        file_path=index_path,
    )

    for report in (
        first,
        second,
    ):
        archive.save(
            report
        )

        relative_path = (
            Path("daily")
            / report.session_date.isoformat()
            / f"{report.report_id}.json"
        )

        index.save(
            report_id=report.report_id,
            session_date=(
                report.session_date.isoformat()
            ),
            semantic_hash=report.semantic_hash,
            archive_path=(
                relative_path.as_posix()
            ),
        )

    first_recovery = (
        recover_task9_daily_reports(
            index=Task9DailyReportIndex(
                official_run_id=RUN_ID,
                file_path=index_path,
            ),
            official_run_id=RUN_ID,
            archive_root=archive_root,
        )
    )

    second_recovery = (
        recover_task9_daily_reports(
            index=Task9DailyReportIndex(
                official_run_id=RUN_ID,
                file_path=index_path,
            ),
            official_run_id=RUN_ID,
            archive_root=archive_root,
        )
    )

    first_progress = (
        build_task9_live_paper_certification_progress_from_raw(
            first_recovery
        )
    )

    second_progress = (
        build_task9_live_paper_certification_progress_from_raw(
            second_recovery
        )
    )

    assert (
        first_progress.to_dict()
        == second_progress.to_dict()
    )

    assert (
        first_progress.nifty.completed_live_paper_trades
        == 2
    )


def test_daily_builder_rejects_prediction_across_midnight():
    report = build_daily(
        report_id="task9-midnight-source",
    )

    # Existing production builder authority has already
    # validated the original report. Rebuild its source
    # prediction on the following calendar day to prove
    # daily session isolation remains fail-closed.
    from dataclasses import replace
    from datetime import timedelta

    from services.reports.paper_certification_daily_report import (
        build_paper_certification_daily_report,
    )
    from tests.r79_reporting_helpers import (
        call_outcome,
        call_prediction,
        counting_decision,
        reconciliation,
        stopped_position,
        wait_outcome,
        wait_prediction,
    )

    call = call_prediction()
    call = replace(
        call,
        requested_at=(
            call.requested_at
            + timedelta(days=1)
        ),
        completed_at=(
            call.completed_at
            + timedelta(days=1)
        ),
        received_at=(
            call.received_at
            + timedelta(days=1)
        ),
        market_timestamp=(
            call.market_timestamp
            + timedelta(days=1)
            if call.market_timestamp
            is not None
            else None
        ),
    )

    wait = wait_prediction()
    position = stopped_position()

    call_result = call_outcome(
        call,
        position,
    )
    wait_result = wait_outcome(
        wait
    )

    with pytest.raises(
        ValueError,
        match="prediction lies outside daily session",
    ):
        build_paper_certification_daily_report(
            report_id="task9-midnight-rejected",
            session_date=report.session_date,
            generated_at=report.generated_at,
            starting_capital=100000.0,
            predictions=(call, wait),
            counting_decisions=(
                counting_decision(call, "midnight"),
                counting_decision(wait, "same-day"),
            ),
            lifecycle_outcomes=(
                call_result,
                wait_result,
            ),
            reconciliations=(
                reconciliation(
                    call,
                    call_result,
                    position,
                ),
                reconciliation(
                    wait,
                    wait_result,
                ),
            ),
            positions=(position,),
        )
