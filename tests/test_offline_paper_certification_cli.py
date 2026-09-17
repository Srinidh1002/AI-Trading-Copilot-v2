"""Task 7 Slice 3 CLI and exit-code contract tests."""
import json

from services.certification.offline_paper_certification_cli import (
    EXIT_BLOCKED_OR_INVALID,
    EXIT_FAILED,
    EXIT_PASSED,
    main,
)


BASE = [
    "--report-id",
    "report-1",
    "--generated-at",
    "2026-08-03T11:10:00+00:00",
    "--branch-name",
    "p10-two-market-weekend-readiness",
    "--commit-sha",
    "3f74eb2",
]


def invoke(tmp_path, *extra):
    output = tmp_path / "certification.json"
    code = main(
        BASE
        + [
            "--output",
            str(output),
        ]
        + list(extra)
    )
    return code, output


def test_cli_passes_and_writes_report(tmp_path, capsys):
    code, output = invoke(tmp_path)

    assert code == EXIT_PASSED
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "PASSED"
    captured = capsys.readouterr()
    assert "PASSED: 6 passed" in captured.out
    assert "report:" in captured.out


def test_cli_failed_exit_code(tmp_path):
    code, output = invoke(
        tmp_path,
        "--failed-check-ids",
        "paper-lifecycle",
    )

    assert code == EXIT_FAILED
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "FAILED"


def test_cli_blocked_exit_code(tmp_path):
    code, output = invoke(
        tmp_path,
        "--blocked-check-ids",
        "operator-dashboard",
    )

    assert code == EXIT_BLOCKED_OR_INVALID
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "BLOCKED"


def test_cli_multiple_ids_are_parsed(tmp_path):
    code, output = invoke(
        tmp_path,
        "--failed-check-ids",
        "paper-lifecycle,two-market-selection",
    )

    assert code == EXIT_FAILED
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["failed_count"] == 2


def test_cli_warnings_are_applied_to_all_checks(tmp_path):
    code, output = invoke(
        tmp_path,
        "--warnings",
        "LOCAL_CLOCK_FIXED,OFFLINE_FIXTURES_ONLY",
    )

    assert code == EXIT_PASSED
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert all(
        check["warnings"]
        == ["LOCAL_CLOCK_FIXED", "OFFLINE_FIXTURES_ONLY"]
        for check in payload["checks"]
    )


def test_cli_unknown_check_returns_invalid_exit(tmp_path, capsys):
    code, output = invoke(
        tmp_path,
        "--failed-check-ids",
        "unknown-check",
    )

    assert code == EXIT_BLOCKED_OR_INVALID
    assert not output.exists()
    assert "unknown certification check" in capsys.readouterr().err


def test_cli_requires_timezone_aware_generated_at(tmp_path):
    output = tmp_path / "report.json"

    code = main(
        [
            "--report-id",
            "report-1",
            "--generated-at",
            "2026-08-03T11:10:00",
            "--branch-name",
            "branch",
            "--commit-sha",
            "abc123",
            "--output",
            str(output),
        ]
    )

    assert code == EXIT_BLOCKED_OR_INVALID
    assert not output.exists()


def test_cli_missing_required_argument_returns_argparse_code():
    code = main([])

    assert code == EXIT_BLOCKED_OR_INVALID
