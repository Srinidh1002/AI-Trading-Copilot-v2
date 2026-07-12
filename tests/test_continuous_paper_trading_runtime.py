import threading

import pytest

from services.continuous_paper_trading_runtime import (
    ContinuousPaperTradingRuntime,
)


# ============================================================
# HELPERS
# ============================================================


class FakeClock:

    def __init__(
        self,
        values=None,
    ):
        self.values = list(
            values
            or []
        )

        self.current = 0.0

    def monotonic(
        self,
    ):
        if self.values:
            self.current = (
                self.values.pop(
                    0
                )
            )

        return self.current


class FakeSleeper:

    def __init__(
        self,
    ):
        self.calls = []

    def __call__(
        self,
        seconds,
    ):
        self.calls.append(
            seconds
        )


def make_runtime(
    *,
    opportunity=None,
    monitoring=None,
    interval_seconds=60,
    clock=None,
    sleeper=None,
):
    if opportunity is None:
        opportunity = (
            lambda: {
                "decision": "NO_TRADE"
            }
        )

    if monitoring is None:
        monitoring = (
            lambda: {
                "status": "COMPLETED"
            }
        )

    if clock is None:
        clock = (
            FakeClock(
                [
                    0.0,
                    1.0,
                    1.0,
                    2.0,
                    2.0,
                    3.0,
                    3.0,
                    4.0,
                ]
            )
        )

    if sleeper is None:
        sleeper = (
            FakeSleeper()
        )

    runtime = (
        ContinuousPaperTradingRuntime(
            opportunity_cycle=(
                opportunity
            ),
            monitoring_cycle=(
                monitoring
            ),
            interval_seconds=(
                interval_seconds
            ),
            sleep_function=(
                sleeper
            ),
            monotonic_function=(
                clock.monotonic
            ),
        )
    )

    return (
        runtime,
        clock,
        sleeper,
    )


# ============================================================
# CONSTRUCTOR
# ============================================================


def test_requires_callable_opportunity():

    with pytest.raises(
        ValueError
    ):
        ContinuousPaperTradingRuntime(
            opportunity_cycle=None,
            monitoring_cycle=lambda: None,
        )


def test_requires_callable_monitoring():

    with pytest.raises(
        ValueError
    ):
        ContinuousPaperTradingRuntime(
            opportunity_cycle=lambda: None,
            monitoring_cycle=None,
        )


def test_requires_callable_sleep():

    with pytest.raises(
        ValueError
    ):
        ContinuousPaperTradingRuntime(
            opportunity_cycle=lambda: None,
            monitoring_cycle=lambda: None,
            sleep_function=None,
        )


def test_requires_callable_monotonic():

    with pytest.raises(
        ValueError
    ):
        ContinuousPaperTradingRuntime(
            opportunity_cycle=lambda: None,
            monitoring_cycle=lambda: None,
            monotonic_function=None,
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        "abc",
        True,
        False,
        -1,
        float(
            "nan"
        ),
        float(
            "inf"
        ),
        float(
            "-inf"
        ),
    ],
)
def test_invalid_interval_rejected(
    value,
):

    with pytest.raises(
        ValueError
    ):
        ContinuousPaperTradingRuntime(
            opportunity_cycle=lambda: None,
            monitoring_cycle=lambda: None,
            interval_seconds=value,
        )


def test_zero_interval_allowed():

    runtime, _, _ = (
        make_runtime(
            interval_seconds=0
        )
    )

    assert (
        runtime.interval_seconds
        == 0.0
    )


def test_numeric_string_interval_allowed():

    runtime, _, _ = (
        make_runtime(
            interval_seconds="30"
        )
    )

    assert (
        runtime.interval_seconds
        == 30.0
    )


# ============================================================
# SINGLE CYCLE
# ============================================================


def test_run_cycle_runs_opportunity():

    calls = []

    def opportunity():
        calls.append(
            "opportunity"
        )

        return {
            "decision": "NO_TRADE"
        }

    runtime, _, _ = (
        make_runtime(
            opportunity=opportunity
        )
    )

    runtime.run_cycle()

    assert (
        "opportunity"
        in calls
    )


def test_run_cycle_runs_monitoring():

    calls = []

    def monitoring():
        calls.append(
            "monitoring"
        )

        return {
            "status": "COMPLETED"
        }

    runtime, _, _ = (
        make_runtime(
            monitoring=monitoring
        )
    )

    runtime.run_cycle()

    assert (
        "monitoring"
        in calls
    )


def test_opportunity_runs_before_monitoring():

    calls = []

    def opportunity():
        calls.append(
            "opportunity"
        )

    def monitoring():
        calls.append(
            "monitoring"
        )

    runtime, _, _ = (
        make_runtime(
            opportunity=opportunity,
            monitoring=monitoring,
        )
    )

    runtime.run_cycle()

    assert calls == [
        "opportunity",
        "monitoring",
    ]


def test_successful_cycle_status():

    runtime, _, _ = (
        make_runtime()
    )

    result = (
        runtime.run_cycle()
    )

    assert (
        result[
            "status"
        ]
        == "COMPLETED"
    )


def test_cycle_number_starts_at_one():

    runtime, _, _ = (
        make_runtime()
    )

    result = (
        runtime.run_cycle()
    )

    assert (
        result[
            "cycle_number"
        ]
        == 1
    )


def test_cycle_numbers_increment():

    runtime, _, _ = (
        make_runtime()
    )

    first = (
        runtime.run_cycle()
    )

    second = (
        runtime.run_cycle()
    )

    assert (
        first[
            "cycle_number"
        ]
        == 1
    )

    assert (
        second[
            "cycle_number"
        ]
        == 2
    )


def test_cycle_returns_operation_results():

    runtime, _, _ = (
        make_runtime(
            opportunity=(
                lambda: {
                    "decision": "TRADE_ALLOWED"
                }
            ),
            monitoring=(
                lambda: {
                    "processed": 2
                }
            ),
        )
    )

    result = (
        runtime.run_cycle()
    )

    assert (
        result[
            "opportunity"
        ][
            "result"
        ][
            "decision"
        ]
        == "TRADE_ALLOWED"
    )

    assert (
        result[
            "monitoring"
        ][
            "result"
        ][
            "processed"
        ]
        == 2
    )


# ============================================================
# ERROR ISOLATION
# ============================================================


def test_opportunity_failure_does_not_stop_monitoring():

    monitoring_calls = []

    def opportunity():
        raise RuntimeError(
            "Opportunity failed"
        )

    def monitoring():
        monitoring_calls.append(
            True
        )

        return {
            "status": "COMPLETED"
        }

    runtime, _, _ = (
        make_runtime(
            opportunity=opportunity,
            monitoring=monitoring,
        )
    )

    result = (
        runtime.run_cycle()
    )

    assert (
        monitoring_calls
        == [
            True
        ]
    )

    assert (
        result[
            "status"
        ]
        == "COMPLETED_WITH_ERRORS"
    )

    assert (
        result[
            "opportunity"
        ][
            "status"
        ]
        == "ERROR"
    )


def test_monitoring_failure_is_captured():

    def monitoring():
        raise RuntimeError(
            "Monitoring failed"
        )

    runtime, _, _ = (
        make_runtime(
            monitoring=monitoring
        )
    )

    result = (
        runtime.run_cycle()
    )

    assert (
        result[
            "status"
        ]
        == "COMPLETED_WITH_ERRORS"
    )

    assert (
        result[
            "monitoring"
        ][
            "error"
        ]
        == "Monitoring failed"
    )


def test_both_operations_can_fail():

    def opportunity():
        raise RuntimeError(
            "Opportunity failed"
        )

    def monitoring():
        raise RuntimeError(
            "Monitoring failed"
        )

    runtime, _, _ = (
        make_runtime(
            opportunity=opportunity,
            monitoring=monitoring,
        )
    )

    result = (
        runtime.run_cycle()
    )

    assert (
        result[
            "status"
        ]
        == "COMPLETED_WITH_ERRORS"
    )

    assert (
        result[
            "opportunity"
        ][
            "status"
        ]
        == "ERROR"
    )

    assert (
        result[
            "monitoring"
        ][
            "status"
        ]
        == "ERROR"
    )


# ============================================================
# STATISTICS
# ============================================================


def test_initial_stats():

    runtime, _, _ = (
        make_runtime()
    )

    stats = (
        runtime.get_stats()
    )

    assert (
        stats[
            "cycles_started"
        ]
        == 0
    )

    assert (
        stats[
            "cycles_completed"
        ]
        == 0
    )

    assert (
        stats[
            "running"
        ]
        is False
    )


def test_successful_cycle_updates_stats():

    runtime, _, _ = (
        make_runtime()
    )

    runtime.run_cycle()

    stats = (
        runtime.get_stats()
    )

    assert (
        stats[
            "cycles_started"
        ]
        == 1
    )

    assert (
        stats[
            "cycles_completed"
        ]
        == 1
    )

    assert (
        stats[
            "opportunity_successes"
        ]
        == 1
    )

    assert (
        stats[
            "monitoring_successes"
        ]
        == 1
    )


def test_failed_operations_update_stats():

    runtime, _, _ = (
        make_runtime(
            opportunity=(
                lambda: (
                    (_ for _ in ())
                    .throw(
                        RuntimeError(
                            "failure"
                        )
                    )
                )
            )
        )
    )

    runtime.run_cycle()

    stats = (
        runtime.get_stats()
    )

    assert (
        stats[
            "opportunity_failures"
        ]
        == 1
    )

    assert (
        stats[
            "cycles_with_errors"
        ]
        == 1
    )


def test_last_cycle_is_recorded():

    runtime, _, _ = (
        make_runtime()
    )

    result = (
        runtime.run_cycle()
    )

    stats = (
        runtime.get_stats()
    )

    assert (
        stats[
            "last_cycle"
        ][
            "cycle_number"
        ]
        == result[
            "cycle_number"
        ]
    )


def test_stats_are_defensive_copy():

    runtime, _, _ = (
        make_runtime()
    )

    runtime.run_cycle()

    stats = (
        runtime.get_stats()
    )

    stats[
        "cycles_started"
    ] = 999

    assert (
        runtime.get_stats()[
            "cycles_started"
        ]
        == 1
    )


def test_reset_stats():

    runtime, _, _ = (
        make_runtime()
    )

    runtime.run_cycle()

    result = (
        runtime.reset_stats()
    )

    assert (
        result[
            "cycles_started"
        ]
        == 0
    )


# ============================================================
# STOP CONTROL
# ============================================================


def test_request_stop():

    runtime, _, _ = (
        make_runtime()
    )

    runtime.request_stop()

    assert (
        runtime.is_stop_requested()
        is True
    )


def test_clear_stop_request():

    runtime, _, _ = (
        make_runtime()
    )

    runtime.request_stop()

    runtime.clear_stop_request()

    assert (
        runtime.is_stop_requested()
        is False
    )


def test_run_with_preexisting_stop_request_runs_no_cycles():

    runtime, _, _ = (
        make_runtime()
    )

    runtime.request_stop()

    stats = (
        runtime.run(
            max_cycles=3
        )
    )

    assert (
        stats[
            "cycles_completed"
        ]
        == 0
    )


# ============================================================
# MAX CYCLES
# ============================================================


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
        True,
        False,
        1.5,
        "2",
    ],
)
def test_invalid_max_cycles_rejected(
    value,
):

    runtime, _, _ = (
        make_runtime()
    )

    with pytest.raises(
        ValueError
    ):
        runtime.run(
            max_cycles=value
        )


def test_max_cycles_one():

    runtime, _, sleeper = (
        make_runtime()
    )

    stats = (
        runtime.run(
            max_cycles=1
        )
    )

    assert (
        stats[
            "cycles_completed"
        ]
        == 1
    )

    assert (
        sleeper.calls
        == []
    )


def test_max_cycles_three():

    runtime, _, _ = (
        make_runtime(
            interval_seconds=0
        )
    )

    stats = (
        runtime.run(
            max_cycles=3
        )
    )

    assert (
        stats[
            "cycles_completed"
        ]
        == 3
    )


# ============================================================
# INTERVAL TIMING
# ============================================================


def test_waits_remaining_interval():

    clock = (
        FakeClock(
            [
                10.0,
            ]
        )
    )

    sleeper = (
        FakeSleeper()
    )

    runtime = (
        ContinuousPaperTradingRuntime(
            opportunity_cycle=(
                lambda: None
            ),
            monitoring_cycle=(
                lambda: None
            ),
            interval_seconds=60,
            sleep_function=sleeper,
            monotonic_function=(
                clock.monotonic
            ),
        )
    )

    remaining = (
        runtime._wait_until_next_cycle(
            0.0
        )
    )

    assert remaining == 50.0

    assert (
        sleeper.calls
        == [
            50.0
        ]
    )


def test_does_not_sleep_when_cycle_exceeds_interval():

    clock = (
        FakeClock(
            [
                70.0
            ]
        )
    )

    sleeper = (
        FakeSleeper()
    )

    runtime = (
        ContinuousPaperTradingRuntime(
            opportunity_cycle=(
                lambda: None
            ),
            monitoring_cycle=(
                lambda: None
            ),
            interval_seconds=60,
            sleep_function=sleeper,
            monotonic_function=(
                clock.monotonic
            ),
        )
    )

    remaining = (
        runtime._wait_until_next_cycle(
            0.0
        )
    )

    assert remaining == 0.0

    assert (
        sleeper.calls
        == []
    )


def test_does_not_sleep_after_stop_request():

    runtime, _, sleeper = (
        make_runtime()
    )

    runtime.request_stop()

    runtime._wait_until_next_cycle(
        0.0
    )

    assert (
        sleeper.calls
        == []
    )


# ============================================================
# KEYBOARD INTERRUPT
# ============================================================


def test_keyboard_interrupt_in_cycle_stops_runtime():

    def opportunity():
        raise KeyboardInterrupt()

    runtime, _, _ = (
        make_runtime(
            opportunity=opportunity,
            interval_seconds=0,
        )
    )

    stats = (
        runtime.run(
            max_cycles=5
        )
    )

    assert (
        stats[
            "interrupted"
        ]
        is True
    )

    assert (
        stats[
            "stop_requested"
        ]
        is True
    )


def test_keyboard_interrupt_in_sleep_stops_runtime():

    class InterruptingSleeper:

        def __call__(
            self,
            seconds,
        ):
            raise KeyboardInterrupt()

    runtime = (
        ContinuousPaperTradingRuntime(
            opportunity_cycle=(
                lambda: None
            ),
            monitoring_cycle=(
                lambda: None
            ),
            interval_seconds=60,
            sleep_function=(
                InterruptingSleeper()
            ),
            monotonic_function=(
                lambda: 0.0
            ),
        )
    )

    stats = (
        runtime.run(
            max_cycles=5
        )
    )

    assert (
        stats[
            "interrupted"
        ]
        is True
    )


# ============================================================
# OVERLAP PROTECTION
# ============================================================


def test_cycle_overlap_is_rejected():

    runtime, _, _ = (
        make_runtime()
    )

    acquired = (
        runtime._cycle_lock.acquire(
            blocking=False
        )
    )

    assert acquired is True

    try:
        with pytest.raises(
            RuntimeError,
            match="already running",
        ):
            runtime.run_cycle()

    finally:
        runtime._cycle_lock.release()


def test_runtime_reentry_is_rejected():

    runtime, _, _ = (
        make_runtime()
    )

    runtime._running = True

    try:
        with pytest.raises(
            RuntimeError,
            match="already running",
        ):
            runtime.run(
                max_cycles=1
            )

    finally:
        runtime._running = False


# ============================================================
# RESULT IMMUTABILITY
# ============================================================


def test_operation_result_is_copied():

    source = {
        "value": {
            "nested": 1
        }
    }

    runtime, _, _ = (
        make_runtime(
            opportunity=(
                lambda: source
            )
        )
    )

    result = (
        runtime.run_cycle()
    )

    result[
        "opportunity"
    ][
        "result"
    ][
        "value"
    ][
        "nested"
    ] = 999

    assert (
        source[
            "value"
        ][
            "nested"
        ]
        == 1
    )


# ============================================================
# RUN FOREVER ALIAS
# ============================================================


def test_run_forever_uses_unlimited_runtime():

    runtime, _, _ = (
        make_runtime(
            interval_seconds=0
        )
    )

    calls = []

    def opportunity():
        calls.append(
            True
        )

        if len(
            calls
        ) >= 2:
            runtime.request_stop()

    runtime.opportunity_cycle = (
        opportunity
    )

    stats = (
        runtime.run_forever()
    )

    assert (
        stats[
            "cycles_completed"
        ]
        == 2
    )

    assert (
        stats[
            "stop_requested"
        ]
        is True
    )