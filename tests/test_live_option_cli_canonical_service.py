import json

from services.canonical import live_option_cli_service as cli


def test_unknown_mode_defaults_to_canonical():
    assert cli.configured_cli_analysis_mode("unexpected") == "canonical"


def test_missing_snapshot_is_structured_error(capsys):
    code = cli.main(["analyse"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 2
    assert "error" in payload


def test_canonical_failure_is_structured(monkeypatch, tmp_path, capsys):
    path = tmp_path / "snapshot.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        cli,
        "from_dashboard_snapshot",
        lambda payload: (_ for _ in ()).throw(ValueError("bad snapshot")),
    )
    code = cli.main(["analyse", "--snapshot-file", str(path)])
    payload = json.loads(capsys.readouterr().out)
    assert code == 2
    assert payload["error"] == "Canonical analysis failed: ValueError."


def test_prepare_failure_is_structured(monkeypatch, tmp_path, capsys):
    path = tmp_path / "snapshot.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        cli,
        "from_dashboard_snapshot",
        lambda payload: (_ for _ in ()).throw(RuntimeError("broken")),
    )
    code = cli.main(["prepare-paper", "--snapshot-file", str(path)])
    payload = json.loads(capsys.readouterr().out)
    assert code == 2
    assert payload["error"] == "Paper candidate preparation failed: RuntimeError."


def test_invalid_candidate_file_is_structured(tmp_path, capsys):
    candidate = tmp_path / "candidate.json"
    decision = tmp_path / "decision.json"
    candidate.write_text("{}", encoding="utf-8")
    decision.write_text("{}", encoding="utf-8")
    code = cli.main([
        "execute-paper",
        "--candidate-file", str(candidate),
        "--decision-file", str(decision),
        "--approve",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert code == 2
    assert "error" in payload
