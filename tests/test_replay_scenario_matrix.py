from pathlib import Path
from dataclasses import replace

import pytest

from services.contracts.final_decision_v1 import DataHealthSummary, FinalDecisionV1
from services.contracts.replay_fixture_v1 import ReplayExpectationsV1, ReplayFixtureV1
from services.replay import load_replay_fixture, run_replay_fixture


FIXTURES = Path(__file__).parent / "fixtures" / "replay"
SCENARIOS = sorted(FIXTURES.glob("*.json"), key=lambda path: path.name)


def _deterministic_decision(snapshot, expectations):
    return FinalDecisionV1(
        decision_id=f"decision-{snapshot.snapshot_id}",
        snapshot_id=snapshot.snapshot_id,
        symbol=snapshot.symbol,
        exchange=snapshot.exchange,
        instrument_type=snapshot.instrument_type,
        created_at=snapshot.captured_at,
        market_timestamp=snapshot.market_timestamp,
        action=expectations.expected_action or "WAIT",
        direction=expectations.expected_direction or "NEUTRAL",
        authorization_status=expectations.expected_authorization or "ANALYSIS_ONLY",
        execution_status=expectations.expected_execution_status or "NOT_REQUESTED",
        market_regime=expectations.expected_market_regime or "UNKNOWN",
        trend_strength=expectations.expected_trend_strength,
        volatility_state=expectations.expected_volatility_state or "UNKNOWN",
        option_type=expectations.expected_option_type,
    )


@pytest.mark.parametrize("fixture_path", SCENARIOS, ids=lambda path: path.stem)
def test_synthetic_nifty_and_sensex_scenario_matrix(fixture_path):
    fixture = load_replay_fixture(fixture_path)

    result = run_replay_fixture(
        fixture,
        pipeline_runner=lambda snapshot: _deterministic_decision(snapshot, fixture.expectations),
    )

    assert fixture.metadata["synthetic"] is True
    assert fixture.metadata["purpose"] == "offline deterministic replay coverage"
    assert result.status == "PASS"


def test_configured_ranges_are_inclusive_and_missing_actual_is_explicit():
    fixture = load_replay_fixture(FIXTURES / "nifty_neutral_valid.json")
    expectations = replace(fixture.expectations, confidence_min=60.0, confidence_max=60.0)
    fixture = replace(fixture, expectations=expectations)
    decision = _deterministic_decision(fixture.snapshot, expectations)

    result = run_replay_fixture(fixture, pipeline_runner=lambda snapshot: decision)

    assert result.status == "INSUFFICIENT_DATA"
    assert [item.field for item in result.mismatches] == ["confidence_max", "confidence_min"]


@pytest.mark.parametrize(
    ("expectations", "changes", "status"),
    [
        (ReplayExpectationsV1(expected_action="BUY"), {"action": "SELL"}, "FAIL"),
        (ReplayExpectationsV1(expected_direction="BULLISH"), {"direction": "BEARISH"}, "FAIL"),
        (ReplayExpectationsV1(expected_authorization="BLOCKED"), {"authorization_status": "ANALYSIS_ONLY"}, "FAIL"),
        (ReplayExpectationsV1(expected_execution_status="REJECTED"), {"execution_status": "NOT_REQUESTED"}, "FAIL"),
        (ReplayExpectationsV1(expected_market_regime="TRENDING"), {"market_regime": "RANGING"}, "FAIL"),
        (ReplayExpectationsV1(expected_trend_strength="HIGH"), {"trend_strength": "LOW"}, "FAIL"),
        (ReplayExpectationsV1(expected_volatility_state="ELEVATED"), {"volatility_state": "LOW"}, "FAIL"),
        (ReplayExpectationsV1(expected_option_type="CE"), {"option_type": "PE"}, "FAIL"),
        (ReplayExpectationsV1(expected_trade_plan_present=True), {}, "FAIL"),
    ],
)
def test_stable_expectation_mismatches_are_failures(expectations, changes, status):
    snapshot = load_replay_fixture(FIXTURES / "nifty_neutral_valid.json").snapshot
    fixture = ReplayFixtureV1("expectation-check", "Expectation check", snapshot, expectations)
    decision = _deterministic_decision(snapshot, expectations)
    decision = replace(decision, **changes)

    assert run_replay_fixture(fixture, pipeline_runner=lambda value: decision).status == status


def test_collections_are_case_insensitive_order_independent_and_allow_additional_actuals():
    snapshot = load_replay_fixture(FIXTURES / "nifty_neutral_valid.json").snapshot
    expectations = ReplayExpectationsV1(
        expected_blockers=("  SNAPSHOT   STALE ",),
        expected_missing_sources=("Options",),
        expected_stale_sources=("Market",),
    )
    fixture = ReplayFixtureV1("collections", "Collection checks", snapshot, expectations)
    decision = FinalDecisionV1(
        snapshot_id=snapshot.snapshot_id, symbol=snapshot.symbol, exchange=snapshot.exchange,
        instrument_type=snapshot.instrument_type, created_at=snapshot.captured_at,
        market_timestamp=snapshot.market_timestamp, action="WAIT",
        blocking_reasons=("snapshot stale", "extra blocker"),
        data_health=DataHealthSummary(missing_sources=("options", "vix"), stale_sources=("market",)),
    )

    assert run_replay_fixture(fixture, pipeline_runner=lambda value: decision).status == "PASS"
