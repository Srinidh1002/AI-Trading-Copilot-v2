"""Task 7A Slice 7 report, launcher and CLI certification."""
import json
from datetime import datetime, timezone

from services.certification.replay_certification_cli import main
from services.certification.repository_replay_certification_launcher import (
    launch_repository_replay_certification,
)


NOW = datetime(2026, 8, 2, 0, 0, tzinfo=timezone.utc)


def test_repository_launcher_writes_passing_report(tmp_path):
    report_path = tmp_path / "report.json"
    report = launch_repository_replay_certification(
        report_path=report_path,
        work_root=tmp_path / "work",
        clock=lambda: NOW,
        git_reader=lambda argument: (
            "test-branch"
            if "abbrev-ref" in argument
            else "abc1234"
        ),
    )

    assert report.overall_status == "PASSED"
    assert report.task_8_ready is True
    assert report.nifty_closed_trades == 60
    assert report.sensex_closed_trades == 60
    assert report.total_closed_trades == 120
    assert report.no_trade_count == 12
    assert report.blocked_count == 12
    assert report.failed_count == 0
    assert report_path.exists()


def test_report_contains_required_distributions(tmp_path):
    report_path = tmp_path / "report.json"
    report = launch_repository_replay_certification(
        report_path=report_path,
        work_root=tmp_path / "work",
        clock=lambda: NOW,
        git_reader=lambda argument: "value",
    )

    assert report.scenario_coverage
    assert report.closure_distribution
    assert set(report.market_realized_pnl) == {
        "NIFTY",
        "SENSEX",
    }
    assert (
        report.total_realized_pnl
        == sum(report.market_realized_pnl.values())
    )


def test_json_artifact_is_stable_and_machine_readable(tmp_path):
    report_path = tmp_path / "report.json"
    report = launch_repository_replay_certification(
        report_path=report_path,
        work_root=tmp_path / "work",
        clock=lambda: NOW,
        git_reader=lambda argument: "value",
    )

    payload = json.loads(
        report_path.read_text(encoding="utf-8")
    )

    assert payload == report.to_dict()
    assert payload["execution_mode"] == "PAPER"
    assert payload["network_access_used"] is False
    assert payload["broker_submission_enabled"] is False
    assert payload["live_execution_eligible"] is False


def test_launcher_is_deterministic_across_clean_roots(tmp_path):
    first = launch_repository_replay_certification(
        report_path=tmp_path / "first.json",
        work_root=tmp_path / "first-work",
        clock=lambda: NOW,
        git_reader=lambda argument: "value",
    )
    second = launch_repository_replay_certification(
        report_path=tmp_path / "second.json",
        work_root=tmp_path / "second-work",
        clock=lambda: NOW,
        git_reader=lambda argument: "value",
    )

    assert first == second


def test_cli_returns_success_for_certified_report(
    tmp_path,
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        "services.certification.replay_certification_cli."
        "launch_repository_replay_certification",
        lambda: type(
            "Report",
            (),
            {
                "overall_status": "PASSED",
                "task_8_ready": True,
                "nifty_closed_trades": 60,
                "sensex_closed_trades": 60,
                "no_trade_count": 12,
                "blocked_count": 12,
                "failed_count": 0,
            },
        )(),
    )

    assert main() == 0
    output = capsys.readouterr().out
    assert "NIFTY=60" in output
    assert "SENSEX=60" in output
    assert "task_8_ready: True" in output


def test_cli_returns_blocked_code_when_not_ready(
    monkeypatch,
):
    monkeypatch.setattr(
        "services.certification.replay_certification_cli."
        "launch_repository_replay_certification",
        lambda: type(
            "Report",
            (),
            {
                "overall_status": "FAILED",
                "task_8_ready": False,
                "nifty_closed_trades": 59,
                "sensex_closed_trades": 60,
                "no_trade_count": 12,
                "blocked_count": 12,
                "failed_count": 0,
            },
        )(),
    )

    assert main() == 1


def test_cli_returns_error_code_on_exception(
    monkeypatch,
):
    def fail():
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "services.certification.replay_certification_cli."
        "launch_repository_replay_certification",
        fail,
    )

    assert main() == 2
