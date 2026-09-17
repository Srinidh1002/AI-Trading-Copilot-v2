from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.paper_orchestration.complete_cycle_execution_context import (
    CompleteCycleAuthoritySetV1,
)
from services.paper_orchestration.complete_cycle_executor import (
    CompletePaperOrchestrationCycleExecutor,
)


NOW = datetime(2026, 1, 8, 9, 30, tzinfo=timezone.utc)
HASH = "a" * 64


def cycle_input():
    value = object.__new__(PaperOrchestrationCycleInputV1)
    object.__setattr__(value, "cycle_id", "cycle-1")
    object.__setattr__(value, "cycle_idempotency_key", "cycle-key-1")
    return value


def clock():
    return NOW


def test_complete_cycle_invokes_authorities_in_exact_order_for_open():
    order = []

    session = SimpleNamespace(
        analysis_allowed=True,
        blockers=(),
        warnings=(),
    )
    opportunity = SimpleNamespace(
        opportunity_status="READY",
        blockers=(),
        warnings=(),
    )
    p6_result = SimpleNamespace(status="READY", blockers=(), warnings=())
    admission = SimpleNamespace(result_id="admission-1")
    lifecycle = SimpleNamespace(
        status="OPEN",
        admission_result=admission,
        entry_result=SimpleNamespace(result_id="entry-1"),
        p8_snapshot=SimpleNamespace(snapshot_id="portfolio-snapshot-1"),
        blockers=(),
        warnings=(),
    )

    authorities = CompleteCycleAuthoritySetV1(
        data_authority=lambda value: order.append("DATA") or object(),
        session_authority=lambda *args: order.append("SESSION") or session,
        analysis_authority=lambda *args: order.append("ANALYSIS") or object(),
        opportunity_authority=lambda *args: (
            order.append("OPPORTUNITY") or opportunity
        ),
        p6_input_factory=lambda *args: order.append("P6_INPUT") or object(),
        new_entry_input_factory=lambda *args: (
            order.append("ENTRY_INPUT") or object()
        ),
    )
    executor = CompletePaperOrchestrationCycleExecutor(
        authorities=authorities,
        p6_stage_authority=lambda value: (
            order.append("P6_PLAN") or p6_result
        ),
        new_entry_stage_authority=lambda value: (
            order.append("NEW_ENTRY") or lifecycle
        ),
        clock=clock,
    )

    with patch.object(
        PaperOrchestrationCycleInputV1,
        "semantic_hash",
        return_value=HASH,
    ):
        result = executor(cycle_input())

    assert result.cycle_status == "COMPLETED"
    assert result.paper_actions == ("OPEN_POSITION",)
    assert tuple(item.stage for item in result.stage_results) == (
        "DATA",
        "SESSION",
        "ANALYSIS",
        "OPPORTUNITY",
        "P6_PLAN",
        "P8_ADMISSION",
        "P7_LIFECYCLE",
        "P8_PORTFOLIO_UPDATE",
    )
    assert order == [
        "DATA",
        "SESSION",
        "ANALYSIS",
        "OPPORTUNITY",
        "P6_INPUT",
        "P6_PLAN",
        "ENTRY_INPUT",
        "NEW_ENTRY",
    ]


def test_no_action_opportunity_stops_before_p6():
    calls = []
    session = SimpleNamespace(
        analysis_allowed=True,
        blockers=(),
        warnings=(),
    )
    opportunity = SimpleNamespace(
        opportunity_status="NO_ACTION",
        blockers=(),
        warnings=("WAIT",),
    )
    authorities = CompleteCycleAuthoritySetV1(
        data_authority=lambda value: object(),
        session_authority=lambda *args: session,
        analysis_authority=lambda *args: object(),
        opportunity_authority=lambda *args: opportunity,
        p6_input_factory=lambda *args: calls.append("P6") or object(),
        new_entry_input_factory=lambda *args: object(),
    )
    executor = CompletePaperOrchestrationCycleExecutor(
        authorities=authorities,
        p6_stage_authority=lambda value: object(),
        new_entry_stage_authority=lambda value: object(),
        clock=clock,
    )

    with patch.object(
        PaperOrchestrationCycleInputV1,
        "semantic_hash",
        return_value=HASH,
    ):
        result = executor(cycle_input())

    assert result.cycle_status == "COMPLETED_NO_ACTION"
    assert result.terminal_stage == "OPPORTUNITY"
    assert calls == []


def test_blocked_session_fails_closed_before_analysis():
    calls = []
    session = SimpleNamespace(
        analysis_allowed=False,
        blockers=("MARKET_CLOSED",),
        warnings=(),
    )
    authorities = CompleteCycleAuthoritySetV1(
        data_authority=lambda value: object(),
        session_authority=lambda *args: session,
        analysis_authority=lambda *args: calls.append("ANALYSIS"),
        opportunity_authority=lambda *args: object(),
        p6_input_factory=lambda *args: object(),
        new_entry_input_factory=lambda *args: object(),
    )
    executor = CompletePaperOrchestrationCycleExecutor(
        authorities=authorities,
        p6_stage_authority=lambda value: object(),
        new_entry_stage_authority=lambda value: object(),
        clock=clock,
    )

    with patch.object(
        PaperOrchestrationCycleInputV1,
        "semantic_hash",
        return_value=HASH,
    ):
        result = executor(cycle_input())

    assert result.cycle_status == "BLOCKED"
    assert result.terminal_stage == "SESSION"
    assert result.blockers == ("MARKET_CLOSED",)
    assert calls == []


def test_authority_exception_becomes_failed_stage():
    authorities = CompleteCycleAuthoritySetV1(
        data_authority=lambda value: (_ for _ in ()).throw(
            RuntimeError("feed down")
        ),
        session_authority=lambda *args: object(),
        analysis_authority=lambda *args: object(),
        opportunity_authority=lambda *args: object(),
        p6_input_factory=lambda *args: object(),
        new_entry_input_factory=lambda *args: object(),
    )
    executor = CompletePaperOrchestrationCycleExecutor(
        authorities=authorities,
        p6_stage_authority=lambda value: object(),
        new_entry_stage_authority=lambda value: object(),
        clock=clock,
    )

    with patch.object(
        PaperOrchestrationCycleInputV1,
        "semantic_hash",
        return_value=HASH,
    ):
        result = executor(cycle_input())

    assert result.cycle_status == "FAILED"
    assert result.terminal_stage == "DATA"
    assert result.errors == ("DATA_AUTHORITY_FAILURE",)
    assert result.stage_results[-1].failure.fail_closed is True
