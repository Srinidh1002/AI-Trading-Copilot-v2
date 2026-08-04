from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import scripts.run_task2_decision_certification as cli
from services.certification.task2_decision_certification_matrix import (
    build_task2_decision_certification_aggregate,
    run_all_task2_decision_certification_scenarios,
)


FORBIDDEN_SENSITIVE_PATTERNS = (
    "Authorization",
    "Bearer",
    "api_key",
    "apiKey",
    "client_code",
    "clientCode",
    "password",
    "access_token",
    "refresh_token",
    "request_headers",
    "raw_headers",
    "raw_payload",
    "provider_payload",
)


def _assert_sensitive_patterns_absent(text: str) -> None:
    assert not any(
        token in text
        for token in FORBIDDEN_SENSITIVE_PATTERNS
    )


def test_cli_runs_all_and_one_scenario_provider_free(
    tmp_path,
    capsys,
):
    aggregate_output = tmp_path / "all.json"

    assert cli.main(
        ["--output", str(aggregate_output)]
    ) == 0

    aggregate_console = capsys.readouterr()

    assert aggregate_console.err == ""
    assert "Task 2 certification: PASS" in aggregate_console.out
    assert "total=19" in aggregate_console.out
    assert "passed=19" in aggregate_console.out
    assert "failed=0" in aggregate_console.out

    aggregate = json.loads(
        aggregate_output.read_text(encoding="utf-8")
    )

    assert aggregate["total_scenarios"] == 19
    assert aggregate["passed_scenarios"] == 19
    assert aggregate["failed_scenarios"] == 0
    assert aggregate["overall_status"] == "PASS"

    single_output = tmp_path / "one.json"

    assert cli.main(
        [
            "--scenario",
            "EQUAL_SCORE_CONFIDENCE_TIE",
            "--output",
            str(single_output),
        ]
    ) == 0

    single_console = capsys.readouterr()

    assert single_console.err == ""
    assert "Task 2 certification: PASS" in single_console.out
    assert "scenario=EQUAL_SCORE_CONFIDENCE_TIE" in (
        single_console.out
    )

    single = json.loads(
        single_output.read_text(encoding="utf-8")
    )

    assert single["scenario_id"] == "EQUAL_SCORE_CONFIDENCE_TIE"
    assert single["certification_status"] == "PASS"


def test_cli_unknown_scenario_returns_two_without_traceback(
    tmp_path,
    capsys,
):
    output = tmp_path / "bad.json"

    exit_code = cli.main(
        [
            "--scenario",
            "DOES_NOT_EXIST",
            "--output",
            str(output),
        ]
    )

    console = capsys.readouterr()

    assert exit_code == 2
    assert console.out == ""
    assert console.err.strip() == (
        "Task 2 certification error: UNKNOWN_SCENARIO"
    )
    assert "Traceback" not in console.err
    assert not output.exists()


def test_cli_import_is_silent():
    root = Path(__file__).resolve().parents[1]

    imported = subprocess.run(
        [
            sys.executable,
            "-c",
            "import scripts.run_task2_decision_certification",
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert imported.returncode == 0
    assert imported.stdout == ""
    assert imported.stderr == ""


def test_cli_subprocess_custom_output_is_provider_free_and_safe(
    tmp_path,
):
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "nested" / "matrix.json"

    run = subprocess.run(
        [
            sys.executable,
            "scripts/run_task2_decision_certification.py",
            "--output",
            str(output),
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert run.returncode == 0
    assert run.stderr == ""
    assert "Task 2 certification: PASS" in run.stdout
    assert "total=19" in run.stdout
    assert output.exists()

    text = output.read_text(encoding="utf-8")

    _assert_sensitive_patterns_absent(text)
    _assert_sensitive_patterns_absent(run.stdout)

    value = json.loads(text)
    safety = dict(value["aggregate_safety_counters"])

    assert safety == {
        "angel_calls": 0,
        "broker_order_invocations": 0,
        "lifecycle_invocations": 0,
        "monitoring_mutations": 0,
        "persistence_mutations": 0,
        "planner_invocations": 0,
        "provider_calls": 0,
        "task6_counter_mutations": 0,
    }


def test_cli_returns_one_for_injected_failed_aggregate(
    monkeypatch,
    tmp_path,
    capsys,
):
    passing = run_all_task2_decision_certification_scenarios()

    failed_result = replace(
        passing.scenario_results[0],
        certification_status="FAILED",
        certification_failure_codes=(
            "CONTROLLED_CERTIFICATION_FAILURE",
        ),
    )

    failed_aggregate = build_task2_decision_certification_aggregate(
        (
            failed_result,
            *passing.scenario_results[1:],
        )
    )

    monkeypatch.setattr(
        cli,
        "run_all_task2_decision_certification_scenarios",
        lambda: failed_aggregate,
    )

    output = tmp_path / "failed.json"

    exit_code = cli.main(["--output", str(output)])
    console = capsys.readouterr()

    assert exit_code == 1
    assert "Task 2 certification: FAILED" in console.out
    assert "failed=1" in console.out
    assert console.err == ""
    assert output.exists()

    value = json.loads(output.read_text(encoding="utf-8"))

    assert value["overall_status"] == "FAILED"
    assert value["failed_scenarios"] == 1
    assert (
        "CONTROLLED_CERTIFICATION_FAILURE"
        in value["scenario_results"][0][
            "certification_failure_codes"
        ]
    )

    _assert_sensitive_patterns_absent(console.out)
    _assert_sensitive_patterns_absent(
        output.read_text(encoding="utf-8")
    )


def test_cli_returns_one_for_injected_safety_failure(
    monkeypatch,
    tmp_path,
    capsys,
):
    passing = run_all_task2_decision_certification_scenarios()
    first = passing.scenario_results[0]

    changed_safety = tuple(
        (
            key,
            1 if key == "provider_calls" else value,
        )
        for key, value in first.safety_counters
    )

    unsafe_result = replace(
        first,
        safety_counters=changed_safety,
    )

    unsafe_aggregate = build_task2_decision_certification_aggregate(
        (
            unsafe_result,
            *passing.scenario_results[1:],
        )
    )

    monkeypatch.setattr(
        cli,
        "run_all_task2_decision_certification_scenarios",
        lambda: unsafe_aggregate,
    )

    output = tmp_path / "unsafe.json"

    exit_code = cli.main(["--output", str(output)])
    console = capsys.readouterr()

    assert exit_code == 1
    assert "Task 2 certification: FAILED" in console.out
    assert console.err == ""

    value = json.loads(output.read_text(encoding="utf-8"))
    safety = dict(value["aggregate_safety_counters"])

    assert value["overall_status"] == "FAILED"
    assert safety["provider_calls"] == 1
    assert "SAFETY_COUNTER_NONZERO" in (
        value["coverage_failure_codes"]
    )


def test_cli_report_write_failure_returns_three_without_raw_error(
    monkeypatch,
    tmp_path,
    capsys,
):
    def fail_write(_output, _payload):
        raise OSError(
            "C:\\private\\sensitive\\filesystem-detail"
        )

    monkeypatch.setattr(
        cli,
        "_write_json_atomic",
        fail_write,
    )

    output = tmp_path / "cannot-write.json"

    exit_code = cli.main(["--output", str(output)])
    console = capsys.readouterr()

    assert exit_code == 3
    assert console.out == ""
    assert console.err.strip() == (
        "Task 2 certification error: REPORT_WRITE_FAILED"
    )
    assert "Traceback" not in console.err
    assert "private" not in console.err
    assert "sensitive" not in console.err
    assert not output.exists()


def test_cli_all_scenario_reports_are_deterministic_across_paths(
    tmp_path,
    capsys,
):
    first_output = tmp_path / "first" / "aggregate.json"
    second_output = tmp_path / "second" / "aggregate.json"

    assert cli.main(
        ["--output", str(first_output)]
    ) == 0
    capsys.readouterr()

    assert cli.main(
        ["--output", str(second_output)]
    ) == 0
    capsys.readouterr()

    first_text = first_output.read_text(encoding="utf-8")
    second_text = second_output.read_text(encoding="utf-8")

    assert first_text == second_text

    first = json.loads(first_text)
    second = json.loads(second_text)

    assert first["deterministic_checksum"] == (
        second["deterministic_checksum"]
    )
    assert first["coverage_summary"] == second["coverage_summary"]
    assert first["aggregate_call_counts"] == (
        second["aggregate_call_counts"]
    )
    assert first["aggregate_safety_counters"] == (
        second["aggregate_safety_counters"]
    )

    assert str(first_output) not in first_text
    assert str(second_output) not in second_text


def test_cli_single_tie_reports_are_deterministic_across_paths(
    tmp_path,
    capsys,
):
    first_output = tmp_path / "first-tie.json"
    second_output = tmp_path / "second-tie.json"

    arguments = [
        "--scenario",
        "EQUAL_SCORE_CONFIDENCE_TIE",
    ]

    assert cli.main(
        [*arguments, "--output", str(first_output)]
    ) == 0
    capsys.readouterr()

    assert cli.main(
        [*arguments, "--output", str(second_output)]
    ) == 0
    capsys.readouterr()

    first_text = first_output.read_text(encoding="utf-8")
    second_text = second_output.read_text(encoding="utf-8")

    assert first_text == second_text

    first = json.loads(first_text)
    second = json.loads(second_text)

    assert first["scenario_id"] == "EQUAL_SCORE_CONFIDENCE_TIE"
    assert first["deterministic_checksum"] == (
        second["deterministic_checksum"]
    )


def test_success_and_failure_console_and_reports_are_secret_free(
    monkeypatch,
    tmp_path,
    capsys,
):
    success_output = tmp_path / "success.json"

    assert cli.main(
        ["--output", str(success_output)]
    ) == 0

    success_console = capsys.readouterr()

    _assert_sensitive_patterns_absent(success_console.out)
    _assert_sensitive_patterns_absent(success_console.err)
    _assert_sensitive_patterns_absent(
        success_output.read_text(encoding="utf-8")
    )

    passing = run_all_task2_decision_certification_scenarios()

    failed_result = replace(
        passing.scenario_results[0],
        certification_status="FAILED",
        certification_failure_codes=(
            "CONTROLLED_FAILURE",
        ),
    )

    failed_aggregate = build_task2_decision_certification_aggregate(
        (
            failed_result,
            *passing.scenario_results[1:],
        )
    )

    monkeypatch.setattr(
        cli,
        "run_all_task2_decision_certification_scenarios",
        lambda: failed_aggregate,
    )

    failure_output = tmp_path / "failure.json"

    assert cli.main(
        ["--output", str(failure_output)]
    ) == 1

    failure_console = capsys.readouterr()

    _assert_sensitive_patterns_absent(failure_console.out)
    _assert_sensitive_patterns_absent(failure_console.err)
    _assert_sensitive_patterns_absent(
        failure_output.read_text(encoding="utf-8")
    )