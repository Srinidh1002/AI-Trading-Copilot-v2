"""
Tests for paper-trading runtime health snapshots.

No broker connection is used.
No real order is placed.
"""

import pytest

from services.paper_trading_runtime_health import (
    PaperTradingRuntimeHealth,
)


class FakeRuntime:

    def __init__(
        self,
        stats,
    ):
        self.stats = stats

    def get_stats(
        self,
    ):
        return self.stats


def make_stats(
    **overrides,
):
    stats = {
        "startup_status": "COMPLETED",
        "startup_result": {
            "success": True,
            "status": "EMPTY",
            "recovered_count": 0,
        },
        "startup_error": None,
        "cycles_started": 1,
        "cycles_completed": 1,
        "cycles_with_errors": 0,
        "opportunity_successes": 1,
        "opportunity_failures": 0,
        "monitoring_successes": 1,
        "monitoring_failures": 0,
        "running": False,
        "interrupted": False,
    }

    stats.update(
        overrides
    )

    return stats


def test_runtime_is_required():
    with pytest.raises(
        ValueError,
        match="runtime is required",
    ):
        PaperTradingRuntimeHealth(
            None
        )


def test_runtime_must_provide_get_stats():

    class InvalidRuntime:
        pass

    with pytest.raises(
        ValueError,
        match="get_stats",
    ):
        PaperTradingRuntimeHealth(
            InvalidRuntime()
        )


def test_get_stats_must_return_dictionary():

    runtime = FakeRuntime(
        None
    )

    health = (
        PaperTradingRuntimeHealth(
            runtime
        )
    )

    with pytest.raises(
        RuntimeError,
        match="dictionary",
    ):
        health.snapshot()


def test_completed_runtime_is_healthy():

    health = (
        PaperTradingRuntimeHealth(
            FakeRuntime(
                make_stats()
            )
        )
    )

    result = health.snapshot()

    assert (
        result["health_status"]
        == "HEALTHY"
    )

    assert (
        result["paper_trading_only"]
        is True
    )

    assert (
        result["real_order_execution"]
        is False
    )

    assert (
        result["total_failures"]
        == 0
    )


def test_startup_failure_is_failed():

    result = (
        PaperTradingRuntimeHealth(
            FakeRuntime(
                make_stats(
                    startup_status=(
                        "FAILED"
                    ),
                    startup_error=(
                        "Recovery failed."
                    ),
                    cycles_started=0,
                    cycles_completed=0,
                )
            )
        ).snapshot()
    )

    assert (
        result["health_status"]
        == "FAILED"
    )

    assert (
        result["startup"]["status"]
        == "FAILED"
    )

    assert (
        result["startup"]["error"]
        == "Recovery failed."
    )


def test_cycle_error_is_degraded():

    result = (
        PaperTradingRuntimeHealth(
            FakeRuntime(
                make_stats(
                    cycles_with_errors=1
                )
            )
        ).snapshot()
    )

    assert (
        result["health_status"]
        == "DEGRADED"
    )


def test_opportunity_failure_is_degraded():

    result = (
        PaperTradingRuntimeHealth(
            FakeRuntime(
                make_stats(
                    opportunity_failures=1
                )
            )
        ).snapshot()
    )

    assert (
        result["health_status"]
        == "DEGRADED"
    )


def test_monitoring_failure_is_degraded():

    result = (
        PaperTradingRuntimeHealth(
            FakeRuntime(
                make_stats(
                    monitoring_failures=1
                )
            )
        ).snapshot()
    )

    assert (
        result["health_status"]
        == "DEGRADED"
    )


def test_not_started_runtime_is_reported():

    result = (
        PaperTradingRuntimeHealth(
            FakeRuntime(
                make_stats(
                    startup_status=(
                        "NOT_STARTED"
                    ),
                    startup_result=None,
                    cycles_started=0,
                    cycles_completed=0,
                )
            )
        ).snapshot()
    )

    assert (
        result["health_status"]
        == "NOT_STARTED"
    )


def test_missing_startup_status_defaults_to_not_started():

    stats = make_stats()

    stats.pop(
        "startup_status"
    )

    stats[
        "cycles_started"
    ] = 0

    result = (
        PaperTradingRuntimeHealth(
            FakeRuntime(
                stats
            )
        ).snapshot()
    )

    assert (
        result["startup"]["status"]
        == "NOT_STARTED"
    )

    assert (
        result["health_status"]
        == "NOT_STARTED"
    )


def test_negative_and_invalid_counters_are_normalized():

    result = (
        PaperTradingRuntimeHealth(
            FakeRuntime(
                make_stats(
                    cycles_started=-5,
                    cycles_completed="invalid",
                    cycles_with_errors=None,
                    opportunity_successes=True,
                    opportunity_failures=-1,
                    monitoring_successes="2",
                    monitoring_failures=False,
                )
            )
        ).snapshot()
    )

    assert result["cycles"] == {
        "started": 0,
        "completed": 0,
        "with_errors": 0,
    }

    assert (
        result["operations"][
            "opportunity_successes"
        ]
        == 0
    )

    assert (
        result["operations"][
            "opportunity_failures"
        ]
        == 0
    )

    assert (
        result["operations"][
            "monitoring_successes"
        ]
        == 2
    )

    assert (
        result["operations"][
            "monitoring_failures"
        ]
        == 0
    )


def test_snapshot_does_not_mutate_runtime_stats():

    original = make_stats()

    runtime = FakeRuntime(
        original
    )

    result = (
        PaperTradingRuntimeHealth(
            runtime
        ).snapshot()
    )

    result[
        "raw_stats"
    ][
        "cycles_started"
    ] = 999

    result[
        "startup"
    ][
        "result"
    ][
        "recovered_count"
    ] = 999

    assert (
        original["cycles_started"]
        == 1
    )

    assert (
        original[
            "startup_result"
        ][
            "recovered_count"
        ]
        == 0
    )


def test_get_health_is_alias_for_snapshot():

    health = (
        PaperTradingRuntimeHealth(
            FakeRuntime(
                make_stats()
            )
        )
    )

    assert (
        health.get_health()
        == health.snapshot()
    )


def test_running_and_interrupted_flags_are_reported():

    result = (
        PaperTradingRuntimeHealth(
            FakeRuntime(
                make_stats(
                    running=True,
                    interrupted=True,
                )
            )
        ).snapshot()
    )

    assert result["running"] is True
    assert result["interrupted"] is True


def test_total_failures_are_aggregated():

    result = (
        PaperTradingRuntimeHealth(
            FakeRuntime(
                make_stats(
                    cycles_with_errors=2,
                    opportunity_failures=3,
                    monitoring_failures=4,
                )
            )
        ).snapshot()
    )

    assert (
        result["total_failures"]
        == 9
    )

    assert (
        result["health_status"]
        == "DEGRADED"
    )