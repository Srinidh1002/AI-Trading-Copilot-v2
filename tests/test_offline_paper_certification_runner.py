"""Task 7 Slice 2 certification runner and JSON output tests."""
from datetime import datetime, timezone
import json

import pytest

from services.certification.offline_paper_certification_runner import (
    load_offline_paper_certification_report,
    run_offline_paper_certification,
    write_offline_paper_certification_report,
)
from services.certification.offline_paper_certification_matrix import (
    build_offline_paper_certification_report,
)


NOW = datetime(2026, 8, 3, 11, 5, tzinfo=timezone.utc)


def run(path, **changes):
    values = dict(
        report_id="report-1",
        generated_at=NOW,
        branch_name="p10-two-market-weekend-readiness",
        commit_sha="05f9666",
        output_path=path,
    )
    values.update(changes)
    return run_offline_paper_certification(**values)


def test_runner_writes_machine_readable_report(tmp_path):
    path = tmp_path / "reports" / "offline-certification.json"

    result = run(path)
    payload = load_offline_paper_certification_report(path)

    assert result.overall_status == "PASSED"
    assert payload["overall_status"] == "PASSED"
    assert payload["passed_count"] == 6
    assert payload["schema_version"] == (
        "offline_paper_certification_report.v1"
    )
    assert payload["execution_mode"] == "PAPER"
    assert payload["network_access_used"] is False
    assert payload["broker_submission_enabled"] is False
    assert payload["live_execution_eligible"] is False


def test_report_output_is_deterministic(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    run(first)
    run(second)

    assert first.read_bytes() == second.read_bytes()


def test_atomic_write_leaves_no_temp_file(tmp_path):
    path = tmp_path / "certification.json"

    run(path)

    assert path.exists()
    assert not path.with_suffix(".json.tmp").exists()


def test_failed_matrix_is_persisted(tmp_path):
    path = tmp_path / "failed.json"

    result = run(
        path,
        failed_check_ids=("paper-lifecycle",),
    )
    payload = load_offline_paper_certification_report(path)

    assert result.overall_status == "FAILED"
    assert payload["failed_count"] == 1
    failed = next(
        check
        for check in payload["checks"]
        if check["check_id"] == "paper-lifecycle"
    )
    assert failed["status"] == "FAILED"


def test_blocked_matrix_is_persisted(tmp_path):
    path = tmp_path / "blocked.json"

    result = run(
        path,
        blocked_check_ids=("operator-dashboard",),
    )

    assert result.overall_status == "BLOCKED"


def test_corrupt_report_fails_closed(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{bad-json", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid"):
        load_offline_paper_certification_report(path)


def test_writer_requires_exact_report_type(tmp_path):
    with pytest.raises(TypeError, match="report"):
        write_offline_paper_certification_report(
            report=object(),
            output_path=tmp_path / "report.json",
        )


def test_json_contains_all_six_checks(tmp_path):
    path = tmp_path / "report.json"

    run(path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert len(payload["checks"]) == 6
    assert {
        check["category"]
        for check in payload["checks"]
    } == {
        "TWO_MARKET",
        "CAPITAL_RISK",
        "PAPER_LIFECYCLE",
        "RESTART_RECOVERY",
        "OPERATOR_DASHBOARD",
        "SAFETY_ISOLATION",
    }


def test_direct_writer_matches_runner_format(tmp_path):
    report = build_offline_paper_certification_report(
        report_id="report-1",
        generated_at=NOW,
        branch_name="branch",
        commit_sha="abc123",
    )
    path = tmp_path / "direct.json"

    write_offline_paper_certification_report(
        report=report,
        output_path=path,
    )

    payload = load_offline_paper_certification_report(path)
    assert payload["report_id"] == "report-1"
    assert payload["commit_sha"] == "abc123"
