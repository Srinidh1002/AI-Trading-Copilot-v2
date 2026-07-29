from datetime import datetime, timezone

import pytest

from services.contracts.market_session_validation_v1 import (
    MarketSessionValidationV1,
)
from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)
from services.contracts.paper_orchestration_failure_v1 import (
    PaperOrchestrationFailureV1,
)
from services.contracts.paper_orchestration_policy_v1 import (
    PaperOrchestrationPolicyV1,
)
from services.contracts.paper_orchestration_stage_result_v1 import (
    PaperOrchestrationStageResultV1,
)


NOW = datetime(2026, 1, 8, 9, 30, tzinfo=timezone.utc)


def make_policy(**changes):
    values = dict(
        orchestration_policy_id="p9-policy-1",
        policy_timestamp=NOW,
    )
    values.update(changes)
    return PaperOrchestrationPolicyV1(**values)


def make_session(**changes):
    values = dict(
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
    values.update(changes)
    return MarketSessionValidationV1(**values)


def make_cycle_input(**changes):
    values = dict(
        cycle_id="cycle-1",
        cycle_idempotency_key="cycle-key-1",
        observation_id="observation-1",
        orchestration_policy=make_policy(),
        underlying_symbol="NIFTY",
        exchange="NSE",
        trading_day_id=NOW.date().isoformat(),
        market_timestamp=NOW,
        received_at=NOW,
        cycle_requested_at=NOW,
        session_validation=make_session(),
        p6_integration_id="p6-integration-1",
        p8_admission_request_id="p8-admission-1",
        p8_admission_idempotency_key="p8-admission-key-1",
        p8_portfolio_event_id="p8-event-1",
        p7_requested_transition_id="p7-transition-1",
        p7_position_id="p7-position-1",
        p7_entry_fill_id="p7-fill-1",
        p8_update_idempotency_key="p8-update-key-1",
        p8_update_event_id="p8-update-event-1",
    )
    values.update(changes)
    return PaperOrchestrationCycleInputV1(**values)


def make_stage(stage="DATA", status="COMPLETED", **changes):
    values = dict(
        stage_result_id=f"stage-{stage.lower()}",
        cycle_id="cycle-1",
        stage=stage,
        status=status,
        started_at=NOW,
        completed_at=NOW,
    )
    values.update(changes)
    return PaperOrchestrationStageResultV1(**values)


def test_policy_is_paper_only():
    policy = make_policy()
    assert policy.execution_mode == "PAPER"
    assert policy.live_execution_eligible is False


@pytest.mark.parametrize(
    "changes",
    [
        {"execution_mode": "LIVE"},
        {"live_execution_eligible": True},
        {"supported_instruments": ("NIFTY",)},
        {"supported_exchanges": ("NSE",)},
    ],
)
def test_policy_rejects_non_p9_configuration(changes):
    with pytest.raises(ValueError):
        make_policy(**changes)


def test_cycle_input_is_deterministic():
    first = make_cycle_input()
    second = make_cycle_input(cycle_id="cycle-2")
    assert first.semantic_hash() == second.semantic_hash()
    assert first.to_json() != second.to_json()


def test_cycle_input_rejects_identity_mismatch():
    with pytest.raises(ValueError):
        make_cycle_input(underlying_symbol="SENSEX")


def test_cycle_input_rejects_live_execution():
    with pytest.raises(ValueError):
        make_cycle_input(execution_mode="LIVE")


def test_failed_stage_requires_failure_evidence():
    with pytest.raises(ValueError):
        make_stage(status="FAILED")


def test_failure_must_fail_closed():
    with pytest.raises(ValueError):
        PaperOrchestrationFailureV1(
            failure_code="PROVIDER_TIMEOUT",
            stage="DATA",
            message="provider timeout",
            retryable=True,
            fail_closed=False,
        )


def test_completed_cycle_result_serializes_deterministically():
    stage = make_stage()
    cycle_input = make_cycle_input()
    result = PaperOrchestrationCycleResultV1(
        cycle_result_id="cycle-result-1",
        cycle_id="cycle-1",
        cycle_idempotency_key="cycle-key-1",
        cycle_input_semantic_hash=cycle_input.semantic_hash(),
        cycle_status="COMPLETED",
        terminal_stage="DATA",
        started_at=NOW,
        completed_at=NOW,
        stage_results=(stage,),
    )
    assert result.execution_mode == "PAPER"
    assert len(result.semantic_hash()) == 64
    assert result.to_json() == result.to_json()


def test_duplicate_cycle_cannot_report_paper_actions():
    cycle_input = make_cycle_input()
    stage = make_stage(status="DUPLICATE_NO_CHANGE")
    with pytest.raises(ValueError):
        PaperOrchestrationCycleResultV1(
            cycle_result_id="cycle-result-2",
            cycle_id="cycle-1",
            cycle_idempotency_key="cycle-key-1",
            cycle_input_semantic_hash=cycle_input.semantic_hash(),
            cycle_status="DUPLICATE_NO_CHANGE",
            terminal_stage="DATA",
            started_at=NOW,
            completed_at=NOW,
            stage_results=(stage,),
            paper_actions=("PAPER_ENTRY",),
            duplicate_of_cycle_result_id="cycle-result-1",
        )


def test_stage_results_must_follow_authoritative_order():
    cycle_input = make_cycle_input()
    with pytest.raises(ValueError):
        PaperOrchestrationCycleResultV1(
            cycle_result_id="cycle-result-3",
            cycle_id="cycle-1",
            cycle_idempotency_key="cycle-key-1",
            cycle_input_semantic_hash=cycle_input.semantic_hash(),
            cycle_status="COMPLETED",
            terminal_stage="DATA",
            started_at=NOW,
            completed_at=NOW,
            stage_results=(
                make_stage("SESSION"),
                make_stage("DATA"),
            ),
        )
