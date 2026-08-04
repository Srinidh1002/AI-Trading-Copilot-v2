"""Task 7 Slice 4 repository certification launcher tests."""
from datetime import datetime, timezone
import json

import pytest

from services.certification.repository_offline_paper_certification_launcher import (
    DEFAULT_CERTIFICATION_REPORT_PATH,
    launch_repository_offline_paper_certification,
)


NOW = datetime(2026, 8, 3, 11, 15, tzinfo=timezone.utc)


class GitReader:
    def __init__(self):
        self.calls = []

    def __call__(self, arguments):
        self.calls.append(arguments)
        if arguments == ("rev-parse", "--abbrev-ref", "HEAD"):
            return "p10-two-market-weekend-readiness\n"
        if arguments == ("rev-parse", "--short", "HEAD"):
            return "cbeb939\n"
        raise AssertionError(arguments)


def launch(tmp_path, **changes):
    reader = changes.pop("git_reader", GitReader())
    values = dict(
        report_id="task-7-certification",
        clock=lambda: NOW,
        output_path=tmp_path / "certification.json",
        git_reader=reader,
    )
    values.update(changes)
    result = launch_repository_offline_paper_certification(**values)
    return result, reader, values["output_path"]


def test_repository_launcher_resolves_local_git_identity(tmp_path):
    result, reader, output = launch(tmp_path)

    assert result.overall_status == "PASSED"
    assert result.branch_name == "p10-two-market-weekend-readiness"
    assert result.commit_sha == "cbeb939"
    assert reader.calls == [
        ("rev-parse", "--abbrev-ref", "HEAD"),
        ("rev-parse", "--short", "HEAD"),
    ]
    assert output.exists()


def test_repository_launcher_writes_fixed_report_shape(tmp_path):
    result, _, output = launch(tmp_path)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result.execution_mode == "PAPER"
    assert payload["network_access_used"] is False
    assert payload["broker_submission_enabled"] is False
    assert payload["live_execution_eligible"] is False
    assert len(payload["checks"]) == 6


def test_repository_launcher_propagates_failed_checks(tmp_path):
    result, _, _ = launch(
        tmp_path,
        failed_check_ids=("paper-lifecycle",),
    )

    assert result.overall_status == "FAILED"
    assert result.failed_count == 1


def test_repository_launcher_propagates_blocked_checks(tmp_path):
    result, _, _ = launch(
        tmp_path,
        blocked_check_ids=("operator-dashboard",),
    )

    assert result.overall_status == "BLOCKED"
    assert result.blocked_count == 1


def test_repository_launcher_requires_aware_clock(tmp_path):
    with pytest.raises(ValueError, match="timezone-aware"):
        launch_repository_offline_paper_certification(
            report_id="report",
            clock=lambda: datetime(2026, 8, 3, 11, 15),
            output_path=tmp_path / "report.json",
            git_reader=GitReader(),
        )


def test_repository_launcher_rejects_blank_git_identity(tmp_path):
    def blank_reader(arguments):
        return "   "

    with pytest.raises(ValueError, match="branch_name"):
        launch_repository_offline_paper_certification(
            report_id="report",
            clock=lambda: NOW,
            output_path=tmp_path / "report.json",
            git_reader=blank_reader,
        )


def test_default_artifact_path_is_repository_relative():
    assert str(DEFAULT_CERTIFICATION_REPORT_PATH).replace("\\", "/") == (
        "artifacts/certification/offline_paper_certification.json"
    )
    assert not DEFAULT_CERTIFICATION_REPORT_PATH.is_absolute()
