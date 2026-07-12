"""
Integration tests connecting:

Continuous runtime health
    -> runtime heartbeat persistence
    -> heartbeat freshness monitoring

No broker connection is used.
No real order is placed.
"""

from datetime import (
    datetime,
    timezone,
)

from run_continuous_paper_trading import (
    create_health_snapshot,
)
from services.continuous_paper_trading_runtime import (
    ContinuousPaperTradingRuntime,
)
from services.paper_trading_heartbeat_monitor import (
    PaperTradingHeartbeatMonitor,
)
from services.paper_trading_runtime_heartbeat import (
    PaperTradingRuntimeHeartbeat,
)


NOW = datetime(
    2026,
    7,
    13,
    10,
    0,
    0,
    tzinfo=timezone.utc,
)


def successful_operation():
    return {
        "success": True,
        "status": "COMPLETED",
    }


def successful_startup():
    return {
        "success": True,
        "status": "RECOVERED",
        "recovered_count": 0,
        "open_count": 0,
        "closed_count": 0,
    }


def make_runtime():
    return (
        ContinuousPaperTradingRuntime(
            opportunity_cycle=(
                successful_operation
            ),
            monitoring_cycle=(
                successful_operation
            ),
            startup_operation=(
                successful_startup
            ),
            interval_seconds=60,
            sleep_function=lambda seconds: None,
        )
    )


def test_runtime_health_can_be_persisted_as_heartbeat(
    tmp_path,
):
    runtime = make_runtime()

    runtime.run(
        max_cycles=1
    )

    health_snapshot = (
        create_health_snapshot(
            runtime
        )
    )

    heartbeat = (
        PaperTradingRuntimeHeartbeat(
            tmp_path / "heartbeat.json",
            clock=lambda: NOW,
        )
    )

    written = heartbeat.write(
        health_snapshot
    )

    assert (
        written["health_snapshot"][
            "health_status"
        ]
        == "HEALTHY"
    )

    assert (
        written["health_snapshot"][
            "real_order_execution"
        ]
        is False
    )


def test_persisted_runtime_heartbeat_is_fresh(
    tmp_path,
):
    runtime = make_runtime()

    runtime.run(
        max_cycles=1
    )

    health_snapshot = (
        create_health_snapshot(
            runtime
        )
    )

    heartbeat = (
        PaperTradingRuntimeHeartbeat(
            tmp_path / "heartbeat.json",
            clock=lambda: NOW,
        )
    )

    heartbeat.write(
        health_snapshot
    )

    monitor = (
        PaperTradingHeartbeatMonitor(
            heartbeat,
            max_age_seconds=180,
            clock=lambda: NOW,
        )
    )

    result = monitor.check()

    assert result["status"] == "FRESH"
    assert result["fresh"] is True

    assert (
        result["health_snapshot"][
            "health_status"
        ]
        == "HEALTHY"
    )


def test_runtime_heartbeat_preserves_paper_only_isolation(
    tmp_path,
):
    runtime = make_runtime()

    runtime.run(
        max_cycles=1
    )

    health_snapshot = (
        create_health_snapshot(
            runtime
        )
    )

    heartbeat = (
        PaperTradingRuntimeHeartbeat(
            tmp_path / "heartbeat.json",
            clock=lambda: NOW,
        )
    )

    heartbeat.write(
        health_snapshot
    )

    loaded = heartbeat.read()

    snapshot = loaded[
        "health_snapshot"
    ]

    assert (
        snapshot["paper_trading_only"]
        is True
    )

    assert (
        snapshot["real_order_execution"]
        is False
    )

    assert (
        snapshot["total_failures"]
        == 0
    )