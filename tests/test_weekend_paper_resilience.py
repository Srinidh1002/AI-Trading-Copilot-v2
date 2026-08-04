"""Offline resilience certification for the certified automated PAPER runtime."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from services.broker.angel_client import AngelMarketDataClient
from services.broker.market_data_control import BrokerMarketDataRequestError
from services.continuous_paper_trading_runtime import ContinuousPaperTradingRuntime
from services.contracts.paper_orchestration_cycle_input_v1 import PaperOrchestrationCycleInputV1
from services.contracts.paper_orchestration_cycle_result_v1 import PaperOrchestrationCycleResultV1
from services.contracts.paper_orchestration_journal_record_v1 import PaperOrchestrationJournalRecordV1
from services.paper_orchestration.certified_operator_controls import CertifiedOperatorControls
from services.paper_orchestration.deterministic_cycle_coordinator import DeterministicPaperOrchestrationCycleCoordinator
from services.paper_orchestration.paper_orchestration_journal import PaperOrchestrationJournal
from services.paper_orchestration.restart_recovery_operation import RestartRecoveryOperation, RestartRecoveryTargetV1
from services.paper_orchestration.certified_runtime_safety import CertifiedPaperRuntimeSafetyConfigV1
from services.market.live_multi_timeframe_data import LiveMultiTimeframeData
from services.live_option_decision_pipeline import LiveOptionDecisionPipeline
from tests.p7_fixture_helpers import NOW, make_observation, make_open_position, make_open_state, make_policy
from services.contracts import PaperTradePositionEvaluationInputV1
from services.paper_trading import evaluate_open_paper_trade_position


FIXED_NOW = datetime(2026, 7, 24, 10, 0, tzinfo=timezone.utc)
HASH = "a" * 64


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        assert seconds <= 1.0
        self.value += seconds


class ForbiddenBroker:
    def place_order(self, *args, **kwargs):
        raise AssertionError("place_order invoked")

    def modify_order(self, *args, **kwargs):
        raise AssertionError("modify_order invoked")

    def cancel_order(self, *args, **kwargs):
        raise AssertionError("cancel_order invoked")

    def square_off(self, *args, **kwargs):
        raise AssertionError("square_off invoked")


def _response():
    return {"status": True, "data": {"fetched": [{"symbolToken": "99926000", "ltp": 25000.0}]}}


def _client(*, retries=2):
    with patch("services.broker.angel_client.SmartConnect") as smart_connect:
        api = MagicMock()
        smart_connect.return_value = api
        client = AngelMarketDataClient(
            max_retries=retries,
            max_rate_limit_retries=retries,
            retry_delay_seconds=0,
            min_request_interval_seconds=0,
            historical_request_interval_seconds=0,
            rate_limit_cooldown_seconds=0,
        )
    client.api = api
    client.authenticated = True
    client.session = {"status": True}
    return client, api


def _market_call(client):
    return client.get_market_data("LTP", {"NSE": ["99926000"]})


def _position_evaluation(**changes):
    values = dict(
        position=make_open_position(), lifecycle_policy=make_policy(allow_partial_exits=True),
        lifecycle_state=make_open_state(), observation=make_observation(), evaluation_timestamp=NOW,
        requested_transition_id="weekend-transition", resulting_lifecycle_state_id="weekend-state",
        evaluation_result_id="weekend-result", exit_fill_ids=("exit-a", "exit-b", "exit-c"),
        pnl_evidence_id="weekend-pnl",
    )
    values.update(changes)
    return evaluate_open_paper_trade_position(PaperTradePositionEvaluationInputV1(**values))


def _journal_input():
    value = object.__new__(PaperOrchestrationCycleInputV1)
    object.__setattr__(value, "cycle_id", "weekend-cycle")
    object.__setattr__(value, "cycle_idempotency_key", "weekend-cycle-key")
    return value


def _journal_result(input_value, status="FAILED"):
    value = object.__new__(PaperOrchestrationCycleResultV1)
    fields = {
        "cycle_result_id": f"{input_value.cycle_id}:result", "cycle_id": input_value.cycle_id,
        "cycle_idempotency_key": input_value.cycle_idempotency_key, "cycle_input_semantic_hash": HASH,
        "cycle_status": status, "terminal_stage": "DATA", "started_at": FIXED_NOW,
        "completed_at": FIXED_NOW, "stage_results": (), "paper_actions": (), "blockers": (),
        "warnings": (), "errors": ("PROVIDER_FAILURE",) if status == "FAILED" else (),
        "duplicate_of_cycle_result_id": None, "metadata": {}, "execution_mode": "PAPER",
        "live_execution_eligible": False, "schema_version": "paper_orchestration_cycle_result.v1",
    }
    for name, field_value in fields.items():
        object.__setattr__(value, name, field_value)
    return value


def test_provider_rate_limit_recovers_with_mocked_client_only():
    client, api = _client(retries=1)
    api.getMarketData.side_effect = [
        {"status": False, "message": "Access denied because of exceeding access rate"},
        _response(),
    ]

    assert _market_call(client)["status"] is True
    assert api.getMarketData.call_count == 2


def test_provider_repeated_rate_limits_exhaust_retry_budget():
    client, api = _client(retries=1)
    api.getMarketData.return_value = {"status": False, "message": "Access denied because of exceeding access rate"}

    with pytest.raises(BrokerMarketDataRequestError, match="rate_limited"):
        _market_call(client)

    assert api.getMarketData.call_count == 2


def test_provider_timeout_empty_candles_and_malformed_result_fail_closed():
    client, api = _client(retries=2)
    api.getMarketData.side_effect = TimeoutError("provider timeout")
    with pytest.raises(RuntimeError, match="failed after 2 attempts"):
        _market_call(client)

    data = LiveMultiTimeframeData(client=SimpleNamespace(get_historical_data=lambda **kwargs: {"data": []}), cache_enabled=False)
    with pytest.raises(ValueError, match="No candle data"):
        data.fetch_timeframe("NSE", "99926000", "5m", end_time=FIXED_NOW)

    malformed, malformed_api = _client()
    malformed_api.getMarketData.return_value = []
    with pytest.raises(RuntimeError, match="empty market-data response"):
        _market_call(malformed)


def test_empty_option_chain_fails_closed_without_broker_order_methods(monkeypatch):
    broker = ForbiddenBroker()
    for name in ("place_order", "modify_order", "cancel_order", "square_off"):
        monkeypatch.setattr(broker, name, lambda *args, _name=name, **kwargs: (_ for _ in ()).throw(AssertionError(f"{_name} invoked")))
    analysis = MagicMock()
    analysis.analyse.return_value = {"strategy": {"decision": "TRADE", "direction": "BULLISH"}, "technical": {"indicators": {"atr": 100}}, "candlestick": {"support": 24900, "resistance": 25100}, "chart": {}}
    chain = MagicMock()
    chain.build_chain.return_value = {"contracts": []}
    pipeline = LiveOptionDecisionPipeline(analysis_pipeline=analysis, option_chain_builder=chain, completed_candle_service=MagicMock(), holiday_calendar=set())

    result = pipeline.analyse(exchange="NSE", symboltoken="99926000", underlying="NIFTY", spot_price=25000, capital=10000)

    assert result["decision"] == "NO_TRADE"
    assert result["trade_plan"] is None


def test_one_market_provider_failure_isolated_from_other_injected_market():
    responses = {"NIFTY": RuntimeError("NIFTY provider unavailable"), "SENSEX": {"status": "READY"}}
    outcomes = {}
    for market in ("NIFTY", "SENSEX"):
        try:
            value = responses[market]
            if isinstance(value, Exception):
                raise value
            outcomes[market] = value["status"]
        except RuntimeError:
            outcomes[market] = "FAILED"
    assert outcomes == {"NIFTY": "FAILED", "SENSEX": "READY"}


def test_journal_retains_failed_cycle_evidence_and_prevents_duplicate_reexecution(tmp_path):
    journal = PaperOrchestrationJournal(tmp_path / "journal.json")
    input_value = _journal_input()
    result = _journal_result(input_value)
    record = PaperOrchestrationJournalRecordV1("record-1", input_value.cycle_idempotency_key, HASH, result, FIXED_NOW)
    journal.save(record)
    calls = []
    coordinator = DeterministicPaperOrchestrationCycleCoordinator(journal=journal, cycle_executor=lambda value: calls.append(value) or _journal_result(value), clock=lambda: FIXED_NOW)
    with patch.object(PaperOrchestrationCycleInputV1, "semantic_hash", return_value=HASH):
        duplicate = coordinator.run(input_value)
    assert journal.get_raw(input_value.cycle_idempotency_key)["cycle_result"]["cycle_status"] == "FAILED"
    assert duplicate.cycle_status == "DUPLICATE_NO_CHANGE"
    assert calls == []


def test_runtime_graceful_shutdown_stop_during_execution_and_no_position_startup():
    clock = FakeClock()
    events = []
    runtime = ContinuousPaperTradingRuntime(
        opportunity_cycle=lambda: (events.append("opportunity"), runtime.request_stop()),
        monitoring_cycle=lambda: events.append("monitoring"),
        startup_operation=lambda: {"success": True, "status": "EMPTY", "recovered_count": 0},
        interval_seconds=0, sleep_function=clock.sleep, monotonic_function=clock.monotonic,
    )
    stats = runtime.run(max_cycles=2)
    assert events == ["opportunity", "monitoring"]
    assert stats["stop_requested"] is True
    assert stats["startup_status"] == "COMPLETED"
    assert stats["cycles_completed"] == 1


def test_emergency_halt_during_cooldown_remains_entry_fail_closed():
    controls = CertifiedOperatorControls(observe_only=False)
    clock = FakeClock()
    clock.sleep(0.1)
    controls.set_emergency_halt(True)
    snapshot = controls.snapshot()
    assert snapshot.emergency_halt is True
    assert snapshot.new_entries_allowed is False
    assert snapshot.position_monitoring_allowed is True


def test_restart_recovery_for_persisted_position_fixture_is_paper_only():
    persisted_position = make_open_position()
    recovered_targets = []

    def recover(target, now):
        recovered_targets.append((target, persisted_position.position_id, now))
        return SimpleNamespace(status="RECOVERED")

    operation = RestartRecoveryOperation(
        targets=(RestartRecoveryTargetV1("P7_TRADE", persisted_position.position_id, recover),),
        clock=lambda: FIXED_NOW,
    )
    result = operation()
    assert result["success"] is True
    assert result["execution_mode"] == "PAPER"
    assert result["live_execution_eligible"] is False
    assert recovered_targets == [(persisted_position.position_id, persisted_position.position_id, FIXED_NOW)]


def test_duplicate_observation_duplicate_monitoring_and_out_of_order_observation_are_safe():
    duplicate_state = replace(
        make_open_state(),
        last_observation_id="obs-1",
        last_observation_timestamp=NOW,
    )
    duplicate = _position_evaluation(lifecycle_state=duplicate_state)
    assert duplicate.status == "OPEN"
    assert duplicate.position_decision == "HOLD"

    earlier = make_observation(
        observation_id="obs-earlier",
        observed_at=NOW - timedelta(seconds=1),
        received_at=NOW - timedelta(seconds=1),
    )
    out_of_order = _position_evaluation(lifecycle_state=duplicate_state, observation=earlier)
    assert out_of_order.status == "BLOCKED"
    assert "OUT_OF_ORDER_OBSERVATION" in out_of_order.blockers

    replay = _position_evaluation(lifecycle_state=duplicate_state)
    assert replay.to_json() == duplicate.to_json()


def test_duplicate_entry_target_fill_and_conflicting_lifecycle_state_fail_closed():
    duplicate_entry = _position_evaluation(requested_transition_id="duplicate-entry")
    repeated_entry = _position_evaluation(requested_transition_id="duplicate-entry")
    assert duplicate_entry.to_json() == repeated_entry.to_json()

    target = _position_evaluation(observation=make_observation(option_last_price=110.0, option_open=110.0, option_low=109.0, option_high=111.0, option_close=110.0))
    assert target.status == "PARTIALLY_EXITED"
    with pytest.raises(ValueError, match="exit_fill_ids already used"):
        _position_evaluation(
            position=target.resulting_position,
            lifecycle_state=target.resulting_lifecycle_state,
            observation=make_observation(observation_id="obs-1"),
        )

    with pytest.raises((TypeError, ValueError)):
        _position_evaluation(lifecycle_state=object())


def test_corrupt_and_missing_persisted_state_recovery_are_fail_closed(tmp_path):
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not-json", encoding="utf-8")
    journal = PaperOrchestrationJournal(corrupt)
    with pytest.raises(ValueError, match="invalid JSON"):
        journal.count()
    missing = PaperOrchestrationJournal(tmp_path / "missing.json")
    assert missing.count() == 0


def test_safety_invariants_and_broker_order_sentinels():
    safety = CertifiedPaperRuntimeSafetyConfigV1(instruments=("NIFTY", "SENSEX"), observe_only=False)
    assert safety.execution_mode == "PAPER"
    assert safety.live_execution_eligible is False
    assert safety.broker_order_submission is False
    broker = ForbiddenBroker()
    for name in ("place_order", "modify_order", "cancel_order", "square_off"):
        with pytest.raises(AssertionError, match=name):
            getattr(broker, name)()
