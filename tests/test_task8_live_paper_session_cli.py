"""Focused CLI tests for the Task 8 PAPER session."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import services.certification.task8_live_paper_session_cli as cli
from services.certification.task8_live_paper_session import (
    Task8LivePaperSessionReportV1,
)


NOW = datetime(2026, 8, 6, 9, 30, tzinfo=timezone.utc)


def _report() -> Task8LivePaperSessionReportV1:
    return Task8LivePaperSessionReportV1(
        session_id="session-cli",
        started_at=NOW,
        completed_at=NOW,
        requested_cycle_count=2,
        completed_cycle_count=2,
        passed_cycle_count=2,
        failed_cycle_count=0,
        total_nifty_evaluation_count=2,
        total_sensex_evaluation_count=2,
        interval_seconds=0.0,
        session_status="PASSED",
        branch="p10-two-market-weekend-readiness",
        commit="92368dc",
        cycle_run_ids=("run-1", "run-2"),
        cycle_report_paths=("one.json", "two.json"),
        blockers=(),
        paper_mode=True,
        broker_submission_disabled=True,
        live_execution_ineligible=True,
    )


def test_cli_returns_zero_for_passed_session(
    tmp_path,
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        cli,
        "_load",
        lambda _: lambda: object(),
    )
    monkeypatch.setattr(
        cli,
        "run_task8_live_paper_session",
        lambda **_: (
            _report(),
            tmp_path / "session-cli-session.json",
        ),
    )

    result = cli.main(
        [
            "--cycle-count",
            "2",
            "--interval-seconds",
            "0",
            "--output-directory",
            str(tmp_path),
            "--session-id",
            "session-cli",
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert '"session_status":"PASSED"' in captured.out
    assert "completed=2/2" in captured.err


def test_cli_returns_two_for_configuration_exception(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        cli,
        "_load",
        lambda _: (_ for _ in ()).throw(
            ValueError("bad factory")
        ),
    )

    result = cli.main([])

    captured = capsys.readouterr()
    assert result == 2
    assert (
        "execution/configuration exception: ValueError"
        in captured.err
    )
