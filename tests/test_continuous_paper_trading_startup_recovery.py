"""
Tests for one-time startup recovery in the
ContinuousPaperTradingRuntime.

No broker connection is used.
No real order is placed.
"""

import pytest

from services.continuous_paper_trading_runtime import (
    ContinuousPaperTradingRuntime,
)


def test_startup_operation_runs_before_first_cycle():
    events = []

    runtime = ContinuousPaperTradingRuntime(
        opportunity_cycle=lambda: events.append(
            "OPPORTUNITY"
        ),
        monitoring_cycle=lambda: events.append(
            "MONITORING"
        ),
        startup_operation=lambda: events.append(
            "STARTUP"
        ),
        interval_seconds=0,
    )

    stats = runtime.run(
        max_cycles=1
    )

    assert events == [
        "STARTUP",
        "OPPORTUNITY",
        "MONITORING",
    ]

    assert stats[
        "startup_status"
    ] == "COMPLETED"


def test_startup_operation_runs_only_once_per_run():
    calls = []

    runtime = ContinuousPaperTradingRuntime(
        opportunity_cycle=lambda: None,
        monitoring_cycle=lambda: None,
        startup_operation=lambda: calls.append(
            "STARTUP"
        ),
        interval_seconds=0,
    )

    runtime.run(
        max_cycles=3
    )

    assert calls == [
        "STARTUP"
    ]


def test_runtime_without_startup_operation_remains_compatible():
    events = []

    runtime = ContinuousPaperTradingRuntime(
        opportunity_cycle=lambda: events.append(
            "OPPORTUNITY"
        ),
        monitoring_cycle=lambda: events.append(
            "MONITORING"
        ),
        interval_seconds=0,
    )

    stats = runtime.run(
        max_cycles=1
    )

    assert events == [
        "OPPORTUNITY",
        "MONITORING",
    ]

    assert stats[
        "startup_status"
    ] == "NOT_CONFIGURED"

    assert stats[
        "cycles_completed"
    ] == 1


def test_startup_result_is_recorded():
    startup_result = {
        "success": True,
        "status": "RECOVERED",
        "recovered_count": 2,
    }

    runtime = ContinuousPaperTradingRuntime(
        opportunity_cycle=lambda: None,
        monitoring_cycle=lambda: None,
        startup_operation=lambda: startup_result,
        interval_seconds=0,
    )

    stats = runtime.run(
        max_cycles=1
    )

    assert stats[
        "startup_status"
    ] == "COMPLETED"

    assert stats[
        "startup_result"
    ] == startup_result

    assert stats[
        "startup_error"
    ] is None


def test_startup_exception_fails_closed():
    events = []

    def failing_startup():
        raise RuntimeError(
            "Recovery failed."
        )

    runtime = ContinuousPaperTradingRuntime(
        opportunity_cycle=lambda: events.append(
            "OPPORTUNITY"
        ),
        monitoring_cycle=lambda: events.append(
            "MONITORING"
        ),
        startup_operation=failing_startup,
        interval_seconds=0,
    )

    stats = runtime.run(
        max_cycles=1
    )

    assert events == []

    assert stats[
        "startup_status"
    ] == "ERROR"

    assert stats[
        "startup_error"
    ] == "Recovery failed."

    assert stats[
        "cycles_started"
    ] == 0

    assert stats[
        "cycles_completed"
    ] == 0


def test_startup_result_success_false_fails_closed():
    events = []

    runtime = ContinuousPaperTradingRuntime(
        opportunity_cycle=lambda: events.append(
            "OPPORTUNITY"
        ),
        monitoring_cycle=lambda: events.append(
            "MONITORING"
        ),
        startup_operation=lambda: {
            "success": False,
            "status": "FAILED",
            "error": "Recovery rejected.",
        },
        interval_seconds=0,
    )

    stats = runtime.run(
        max_cycles=1
    )

    assert events == []

    assert stats[
        "startup_status"
    ] == "FAILED"

    assert stats[
        "cycles_started"
    ] == 0


def test_empty_recovery_result_is_allowed():
    events = []

    runtime = ContinuousPaperTradingRuntime(
        opportunity_cycle=lambda: events.append(
            "OPPORTUNITY"
        ),
        monitoring_cycle=lambda: events.append(
            "MONITORING"
        ),
        startup_operation=lambda: {
            "success": True,
            "status": "EMPTY",
            "recovered_count": 0,
        },
        interval_seconds=0,
    )

    stats = runtime.run(
        max_cycles=1
    )

    assert events == [
        "OPPORTUNITY",
        "MONITORING",
    ]

    assert stats[
        "startup_status"
    ] == "COMPLETED"

    assert stats[
        "cycles_completed"
    ] == 1


def test_startup_operation_must_be_callable():
    with pytest.raises(
        ValueError,
        match=(
            "startup_operation must be callable"
        ),
    ):
        ContinuousPaperTradingRuntime(
            opportunity_cycle=lambda: None,
            monitoring_cycle=lambda: None,
            startup_operation="invalid",
        )


def test_none_startup_operation_is_valid():
    runtime = ContinuousPaperTradingRuntime(
        opportunity_cycle=lambda: None,
        monitoring_cycle=lambda: None,
        startup_operation=None,
        interval_seconds=0,
    )

    stats = runtime.run(
        max_cycles=1
    )

    assert stats[
        "startup_status"
    ] == "NOT_CONFIGURED"

    assert stats[
        "cycles_completed"
    ] == 1


def test_reset_stats_resets_startup_state():
    runtime = ContinuousPaperTradingRuntime(
        opportunity_cycle=lambda: None,
        monitoring_cycle=lambda: None,
        startup_operation=lambda: {
            "success": True,
            "status": "EMPTY",
        },
        interval_seconds=0,
    )

    runtime.run(
        max_cycles=1
    )

    runtime.reset_stats()

    stats = runtime.get_stats()

    assert stats[
        "startup_status"
    ] == "NOT_RUN"

    assert stats[
        "startup_result"
    ] is None

    assert stats[
        "startup_error"
    ] is None