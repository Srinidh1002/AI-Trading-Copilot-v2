import json

from services.contracts.final_decision_v1 import FinalDecisionV1
from services.replay import run_replay_directory


def _payload(fixture_id="fixture-a"):
    return {
        "schema_version": "replay_fixture.v1", "fixture_id": fixture_id,
        "name": fixture_id,
        "snapshot": {"schema_version": "market_snapshot.v1", "snapshot_id": fixture_id,
            "symbol": "NIFTY", "exchange": "NSE", "instrument_type": "INDEX",
            "captured_at": "2026-07-24T09:30:00+05:30",
            "market_timestamp": "2026-07-24T09:30:00+05:30", "ltp": 25000,
            "timeframes": {}},
        "expectations": {"expected_action": "WAIT"},
        "metadata": {"synthetic": True, "purpose": "offline deterministic replay coverage"},
    }


def _wait(snapshot):
    return FinalDecisionV1(
        snapshot_id=snapshot.snapshot_id, symbol=snapshot.symbol, exchange=snapshot.exchange,
        instrument_type=snapshot.instrument_type, created_at=snapshot.captured_at,
        market_timestamp=snapshot.market_timestamp, action="WAIT",
    )


def test_directory_runner_sorts_json_and_isolates_malformed_fixture(tmp_path):
    (tmp_path / "z.json").write_text(json.dumps(_payload("z")), encoding="utf-8")
    (tmp_path / "a.json").write_text("{", encoding="utf-8")
    (tmp_path / "ignored.txt").write_text("not a fixture", encoding="utf-8")

    result = run_replay_directory(tmp_path, pipeline_runner_by_fixture={"z": _wait})

    assert [item.fixture_name for item in result.results] == ["a.json", "z"]
    assert [item.status for item in result.results] == ["ERROR", "PASS"]
    assert result.total == result.passed + result.failed + result.insufficient_data + result.errors
    assert str(tmp_path) not in result.to_json()


def test_directory_runner_empty_and_invalid_paths_fail_safely(tmp_path):
    empty = run_replay_directory(tmp_path)
    invalid = run_replay_directory(tmp_path / "missing")

    assert empty.total == 0
    assert empty.warnings == ("No matching replay fixtures were found.",)
    assert invalid.errors == 1

    file_path = tmp_path / "fixture.json"
    file_path.write_text(json.dumps(_payload()), encoding="utf-8")
    assert run_replay_directory(file_path).errors == 1


def test_directory_runner_filename_fallback_selects_runner(tmp_path):
    (tmp_path / "named.json").write_text(json.dumps(_payload("fixture-id")), encoding="utf-8")

    result = run_replay_directory(tmp_path, pipeline_runner_by_fixture={"named.json": _wait})

    assert result.passed == 1
    assert result.semantic_dict() == run_replay_directory(
        tmp_path, pipeline_runner_by_fixture={"named.json": _wait}
    ).semantic_dict()


def test_directory_runner_counts_pass_fail_and_insufficient_data(tmp_path):
    for name, expectation in (("pass", "WAIT"), ("fail", "BUY"), ("insufficient", "WAIT")):
        payload = _payload(name)
        payload["expectations"] = {"expected_action": expectation}
        if name == "insufficient":
            payload["expectations"] = {"confidence_min": 1}
        (tmp_path / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")

    result = run_replay_directory(
        tmp_path,
        pipeline_runner_by_fixture={"pass": _wait, "fail": _wait, "insufficient": _wait},
    )

    assert (result.passed, result.failed, result.insufficient_data, result.errors) == (1, 1, 1, 0)
