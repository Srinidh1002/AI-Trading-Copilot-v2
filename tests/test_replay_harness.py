import json

from services.contracts.final_decision_v1 import FinalDecisionV1
from services.contracts.market_snapshot_v1 import MarketSnapshotV1
from services.contracts.replay_fixture_v1 import ReplayExpectationsV1, ReplayFixtureV1
from services.replay import evaluate_replay_expectations, load_replay_fixture, run_replay_fixture


def _snapshot() -> MarketSnapshotV1:
    return MarketSnapshotV1(
        snapshot_id="replay-snapshot",
        symbol="NIFTY",
        exchange="NSE",
        instrument_type="INDEX",
        captured_at="2026-07-24T09:30:00+05:30",
        market_timestamp="2026-07-24T09:30:00+05:30",
        ltp=25000,
    )


def _decision() -> FinalDecisionV1:
    return FinalDecisionV1(
        decision_id="generated-per-run",
        snapshot_id="replay-snapshot",
        symbol="NIFTY",
        exchange="NSE",
        instrument_type="INDEX",
        created_at="2026-07-24T09:30:01+05:30",
        market_timestamp="2026-07-24T09:30:00+05:30",
        action="WAIT",
        authorization_status="ANALYSIS_ONLY",
        execution_status="NOT_REQUESTED",
        direction="NEUTRAL",
    )


def _fixture() -> ReplayFixtureV1:
    return ReplayFixtureV1(
        fixture_id="neutral-wait",
        name="Neutral decision remains analysis-only",
        snapshot=_snapshot(),
        expectations=ReplayExpectationsV1(
            action="WAIT",
            authorization_status="ANALYSIS_ONLY",
            execution_status="NOT_REQUESTED",
            direction="NEUTRAL",
            validation_passed=True,
        ),
    )


def test_replay_fixture_json_round_trip_and_loader(tmp_path):
    fixture = _fixture()
    fixture_path = tmp_path / "neutral-wait.json"
    fixture_path.write_text(fixture.to_json(), encoding="utf-8")

    loaded = load_replay_fixture(fixture_path)

    assert loaded.to_dict() == fixture.to_dict()
    assert json.loads(loaded.to_json())["schema_version"] == "replay_fixture.v1"


def test_replay_evaluation_uses_only_explicit_stable_expectations():
    result = evaluate_replay_expectations(_fixture(), _decision())

    assert result.passed is True
    assert result.mismatches == ()
    assert result.decision.decision_id == "generated-per-run"


def test_replay_evaluation_reports_typed_mismatch():
    fixture = ReplayFixtureV1(
        fixture_id="expected-buy",
        name="Intentional mismatch",
        snapshot=_snapshot(),
        expectations=ReplayExpectationsV1(action="BUY"),
    )

    result = run_replay_fixture(fixture, pipeline_runner=lambda snapshot: _decision())

    assert result.passed is False
    assert result.mismatches[0].field == "action"
    assert result.mismatches[0].expected == "BUY"
    assert result.mismatches[0].actual == "WAIT"
