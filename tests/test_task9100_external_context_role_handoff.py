from types import SimpleNamespace

from services.certification.task9_live_candidate_adapter import (
    _task9_external_context_for_decision,
)
from services.certification.task9_subsystem_role_authority import (
    Task9SubsystemId,
    default_task9_subsystem_role_registry,
)


def _context(status):
    return SimpleNamespace(
        context_status=status,
    )


def test_current_task9_external_subsystems_are_nonblocking_when_absent():
    registry = {
        row.subsystem_id: row
        for row
        in default_task9_subsystem_role_registry()
    }

    for subsystem_id in (
        Task9SubsystemId.GLOBAL_MARKETS,
        Task9SubsystemId.INSTITUTIONAL_FLOWS,
        Task9SubsystemId.SCHEDULED_EVENTS,
    ):
        assert (
            registry[subsystem_id].decision_blocking
            is False
        )


def test_unavailable_nonblocking_external_context_is_omitted_from_decision():
    unavailable = _context(
        "UNAVAILABLE"
    )

    assert (
        _task9_external_context_for_decision(
            unavailable
        )
        is None
    )


def test_ready_optional_external_context_remains_available_to_decision():
    ready = _context(
        "READY"
    )

    assert (
        _task9_external_context_for_decision(
            ready
        )
        is ready
    )


def test_ready_with_warnings_optional_context_remains_available():
    ready = _context(
        "READY_WITH_WARNINGS"
    )

    assert (
        _task9_external_context_for_decision(
            ready
        )
        is ready
    )


def test_blocked_external_context_is_never_suppressed():
    blocked = _context(
        "BLOCKED"
    )

    assert (
        _task9_external_context_for_decision(
            blocked
        )
        is blocked
    )


def test_conflicting_external_context_is_never_suppressed():
    conflicting = _context(
        "CONFLICTING"
    )

    assert (
        _task9_external_context_for_decision(
            conflicting
        )
        is conflicting
    )


def test_unknown_external_status_fails_safe_by_remaining_supplied():
    malformed = SimpleNamespace(
        context_status="SOMETHING_NEW"
    )

    assert (
        _task9_external_context_for_decision(
            malformed
        )
        is malformed
    )
