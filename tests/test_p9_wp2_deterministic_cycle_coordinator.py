from datetime import datetime, timedelta, timezone

from services.contracts.market_session_validation_v1 import (
    MarketSessionValidationV1,
)
from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)
from services.contracts.paper_orchestration_policy_v1 import (
    PaperOrchestrationPolicyV1,
)
from services.contracts.paper_orchestration_stage_result_v1 import (
    PaperOrchestrationStageResultV1,
)
from services.paper_orchestration.deterministic_cycle_coordinator import (
    DeterministicPaperOrchestrationCycleCoordinator,
)
from services.paper_orchestration.paper_orchestration_journal import (
    PaperOrchestrationJournal,
)


NOW = datetime(2026, 1, 8, 9, 30, tzinfo=timezone.utc)


class StepClock:
    def __init__(self):
        self.value = NOW

    def __call__(self):
        result = self.value
        self.value += timedelta(milliseconds=1)
        return result


def make_policy():
    return PaperOrchestrationPolicyV1(
        orchestration_policy_id="policy-1",
        policy_timestamp=NOW,
    )


def make_session():
    return MarketSessionValidationV1(
        validation_id="session-1",
        evaluated_at=NOW,
        market_timestamp=NOW,
        symbol="NIFTY",
        exchange="NSE",
        timezone="Asia/Kolkata",
        trading_date=NOW.date(),
        session_state="REGULAR",
        session_phase="REGULAR_TRADING",
        trading_day_status="TRADING_DAY",
        is_trading_day=True,
        regular_session_open=True,
        analysis_allowed=True,
        paper_preparation_allowed=True,
        paper_execution_allowed=True,
    )


def make_input(observation_id="observation-1"):
    return PaperOrchestrationCycleInputV1(
        cycle_id="cycle-1",
        cycle_idempotency_key="cycle-key-1",
        observation_id=observation_id,
        orchestration_policy=make_policy(),
        underlying_symbol="NIFTY",
        exchange="NSE",
        trading_day_id=NOW.date().isoformat(),
        market_timestamp=NOW,
        received_at=NOW,
        cycle_requested_at=NOW,
        session_validation=make_session(),
        p6_integration_id="p6-1",
        p8_admission_request_id="p8-admission-1",
        p8_admission_idempotency_key="p8-admission-key-1",
        p8_portfolio_event_id="p8-event-1",
        p7_requested_transition_id="p7-transition-1",
        p7_position_id="p7-position-1",
        p7_entry_fill_id="p7-entry-fill-1",
        p8_update_idempotency_key="p8-update-key-1",
        p8_update_event_id="p8-update-event-1",
    )


def completed_executor(cycle_input):
    stage = PaperOrchestrationStageResultV1(
        stage_result_id="stage-data",
        cycle_id=cycle_input.cycle_id,
        stage="DATA",
        status="COMPLETED",
        started_at=NOW,
        completed_at=NOW,
    )
    return PaperOrchestrationCycleResultV1(
        cycle_result_id="cycle-result-1",
        cycle_id=cycle_input.cycle_id,
        cycle_idempotency_key=cycle_input.cycle_idempotency_key,
        cycle_input_semantic_hash=cycle_input.semantic_hash(),
        cycle_status="COMPLETED",
        terminal_stage="DATA",
        started_at=NOW,
        completed_at=NOW,
        stage_results=(stage,),
    )


def make_coordinator(tmp_path, executor=completed_executor):
    return DeterministicPaperOrchestrationCycleCoordinator(
        journal=PaperOrchestrationJournal(
            tmp_path / "journal.json"
        ),
        cycle_executor=executor,
        clock=StepClock(),
    )


def test_new_cycle_executes_and_journals_once(tmp_path):
    calls = []

    def executor(value):
        calls.append(value.cycle_id)
        return completed_executor(value)

    coordinator = make_coordinator(tmp_path, executor)
    result = coordinator.run(make_input())

    assert result.cycle_status == "COMPLETED"
    assert calls == ["cycle-1"]
    assert coordinator.journal.count() == 1


def test_same_payload_duplicate_does_not_reexecute(tmp_path):
    calls = []

    def executor(value):
        calls.append(value.cycle_id)
        return completed_executor(value)

    coordinator = make_coordinator(tmp_path, executor)
    first = coordinator.run(make_input())
    second = coordinator.run(make_input())

    assert first.cycle_status == "COMPLETED"
    assert second.cycle_status == "DUPLICATE_NO_CHANGE"
    assert second.duplicate_of_cycle_result_id == first.cycle_result_id
    assert calls == ["cycle-1"]
    assert coordinator.journal.count() == 1


def test_payload_conflict_fails_closed_without_execution(tmp_path):
    calls = []

    def executor(value):
        calls.append(value.observation_id)
        return completed_executor(value)

    coordinator = make_coordinator(tmp_path, executor)
    coordinator.run(make_input("observation-1"))
    conflict = coordinator.run(make_input("observation-2"))

    assert conflict.cycle_status == "FAILED"
    assert conflict.errors == ("IDEMPOTENCY_PAYLOAD_CONFLICT",)
    assert calls == ["observation-1"]
    assert coordinator.journal.count() == 1


def test_executor_exception_becomes_journaled_failure(tmp_path):
    def executor(_):
        raise RuntimeError("provider failed")

    coordinator = make_coordinator(tmp_path, executor)
    result = coordinator.run(make_input())

    assert result.cycle_status == "FAILED"
    assert result.errors == ("CYCLE_EXECUTOR_FAILURE",)
    assert coordinator.journal.count() == 1


def test_invalid_executor_result_fails_closed(tmp_path):
    def executor(cycle_input):
        result = completed_executor(cycle_input)
        object.__setattr__(result, "cycle_id", "wrong-cycle")
        return result

    coordinator = make_coordinator(tmp_path, executor)
    result = coordinator.run(make_input())

    assert result.cycle_status == "FAILED"
    assert result.errors == ("CYCLE_EXECUTOR_FAILURE",)
    assert coordinator.journal.count() == 1


def test_duplicate_result_never_reports_paper_action(tmp_path):
    coordinator = make_coordinator(tmp_path)
    coordinator.run(make_input())
    duplicate = coordinator.run(make_input())

    assert duplicate.paper_actions == ()
    assert all(
        not stage.paper_action_occurred
        for stage in duplicate.stage_results
    )
