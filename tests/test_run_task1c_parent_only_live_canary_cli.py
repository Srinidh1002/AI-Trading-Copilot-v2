from services.certification.task1c_parent_only_live_canary_cli import main
from services.certification.task1c_parent_only_live_canary import Task1CParentOnlyDependenciesV1
from datetime import datetime, timezone


def test_cli_requires_confirmation_before_loading_live_dependencies(monkeypatch, capsys):
    monkeypatch.setattr("services.certification.task1c_parent_only_live_canary_cli.build_task1c_parent_only_dependencies", lambda: (_ for _ in ()).throw(AssertionError("provider composition")))
    assert main([]) == 2
    assert "confirm-live-read" in capsys.readouterr().err


def test_cli_sanitizes_parent_validation_failure(monkeypatch, capsys):
    now = datetime(2026, 8, 3, tzinfo=timezone.utc)
    dependency = Task1CParentOnlyDependenciesV1("branch", "commit", lambda: (_ for _ in ()).throw(ValueError("jwt=never-print")), lambda: now, lambda: "run")
    monkeypatch.setattr("services.certification.task1c_parent_only_live_canary_cli.build_task1c_parent_only_dependencies", lambda: dependency)
    assert main(["--confirm-live-read"]) == 1
    output = capsys.readouterr().err
    assert "PARENT_EVALUATION_FAILED" in output and "VALIDATION_VALUE_ERROR" in output
    assert "never-print" not in output and "jwt" not in output
