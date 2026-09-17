from datetime import datetime, timedelta, timezone

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


def policy(**changes):
    values = {
        "orchestration_policy_id": "policy-1",
        "policy_timestamp": NOW,
    }
    values.update(changes)
    return PaperOrchestrationPolicyV1(**values)


def session(**changes):
    values = {
        "validation_id": "session-1",
        "evaluated_at": NOW,
        "market_timestamp": NOW,
        "symbol": "NIFTY",
        "exchange": "NSE",
        "timezone": "Asia/Kolkata",
        "trading_date": NOW.date(),
        "session_state": "REGULAR",
        "session_phase": "REGULAR_TRADING",
        "trading_day_status": "TRADING_DAY",
        "is_trading_day": True,
        "regular_session_open": True,
        "analysis_allowed": True,
        "paper_preparation_allowed": True,
        "paper_execution_allowed": True,
    }
    values.update(changes)
    return MarketSessionValidationV1(**values)


def cycle_input(**changes):
    values = {
        "cycle_id": "cycle-1",
        "cycle_idempotency_key": "cycle-key-1",
        "observation_id": "observation-1",
        "orchestration_policy": policy(),
        "underlying_symbol": "NIFTY",
        "exchange": "NSE",
        "trading_day_id": NOW.date().isoformat(),
        "market_timestamp": NOW,
        "received_at": NOW,
        "cycle_requested_at": NOW,
        "session_validation": session(),
        "p6_integration_id": "p6-1",
        "p8_admission_request_id": "p8-admission-1",
        "p8_admission_idempotency_key": "p8-admission-key-1",
        "p8_portfolio_event_id": "p8-event-1",
        "p7_requested_transition_id": "p7-transition-1",
        "p7_position_id": "p7-position-1",
        "p7_entry_fill_id": "p7-fill-1",
        "p8_update_idempotency_key": "p8-update-key-1",
        "p8_update_event_id": "p8-update-event-1",
    }
    values.update(changes)
    return PaperOrchestrationCycleInputV1(**values)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("cycle_id", ""),
        ("cycle_idempotency_key", ""),
        ("observation_id", ""),
        ("p6_integration_id", ""),
        ("p8_admission_request_id", ""),
        ("p7_requested_transition_id", ""),
    ],
)
def test_cycle_input_rejects_blank_authoritative_identity(field, value):
    with pytest.raises(ValueError):
        cycle_input(**{field: value})


@pytest.mark.parametrize(
    "changes",
    [
        {"received_at": NOW - timedelta(seconds=1)},
        {"cycle_requested_at": NOW - timedelta(seconds=1)},
        {
            "cycle_requested_at": NOW + timedelta(seconds=121),
        },
        {
            "market_timestamp": NOW + timedelta(seconds=6),
            "received_at": NOW + timedelta(seconds=6),
            "cycle_requested_at": NOW,
            "session_validation": session(
                market_timestamp=NOW + timedelta(seconds=6),
            ),
            "trading_day_id": (NOW + timedelta(seconds=6)).date().isoformat(),
        },
    ],
)
def test_cycle_input_rejects_invalid_time_relationships(changes):
    with pytest.raises(ValueError):
        cycle_input(**changes)


@pytest.mark.parametrize(
    ("stage", "status"),
    [
        ("DATA", "COMPLETED"),
        ("SESSION", "BLOCKED"),
        ("ANALYSIS", "NO_ACTION"),
        ("OPPORTUNITY", "DUPLICATE_NO_CHANGE"),
        ("P6_PLAN", "COMPLETED"),
        ("P8_ADMISSION", "BLOCKED"),
        ("P7_LIFECYCLE", "COMPLETED"),
        ("P8_PORTFOLIO_UPDATE", "COMPLETED"),
        ("PERSISTENCE", "COMPLETED"),
    ],
)
def test_stage_status_matrix(stage, status):
    result = PaperOrchestrationStageResultV1(
        stage_result_id=f"stage-{stage}",
        cycle_id="cycle-1",
        stage=stage,
        status=status,
        started_at=NOW,
        completed_at=NOW,
    )
    assert result.stage == stage
    assert result.status == status


@pytest.mark.parametrize(
    "stage",
    [
        "DATA",
        "SESSION",
        "ANALYSIS",
        "OPPORTUNITY",
        "P6_PLAN",
        "P8_ADMISSION",
        "P7_LIFECYCLE",
        "P8_PORTFOLIO_UPDATE",
        "PERSISTENCE",
        "RUNTIME",
    ],
)
def test_failure_stage_matrix(stage):
    failure = PaperOrchestrationFailureV1(
        failure_code="TEST_FAILURE",
        stage=stage,
        message="failure",
        retryable=False,
    )
    assert failure.stage == stage


def test_failed_cycle_requires_failed_stage():
    current = cycle_input()
    stage = PaperOrchestrationStageResultV1(
        stage_result_id="stage-data",
        cycle_id="cycle-1",
        stage="DATA",
        status="COMPLETED",
        started_at=NOW,
        completed_at=NOW,
    )
    with pytest.raises(ValueError):
        PaperOrchestrationCycleResultV1(
            cycle_result_id="result-1",
            cycle_id="cycle-1",
            cycle_idempotency_key="cycle-key-1",
            cycle_input_semantic_hash=current.semantic_hash(),
            cycle_status="FAILED",
            terminal_stage="DATA",
            started_at=NOW,
            completed_at=NOW,
            stage_results=(stage,),
        )


def test_blocked_cycle_requires_blocked_stage():
    current = cycle_input()
    stage = PaperOrchestrationStageResultV1(
        stage_result_id="stage-data",
        cycle_id="cycle-1",
        stage="DATA",
        status="COMPLETED",
        started_at=NOW,
        completed_at=NOW,
    )
    with pytest.raises(ValueError):
        PaperOrchestrationCycleResultV1(
            cycle_result_id="result-1",
            cycle_id="cycle-1",
            cycle_idempotency_key="cycle-key-1",
            cycle_input_semantic_hash=current.semantic_hash(),
            cycle_status="BLOCKED",
            terminal_stage="DATA",
            started_at=NOW,
            completed_at=NOW,
            stage_results=(stage,),
        )
