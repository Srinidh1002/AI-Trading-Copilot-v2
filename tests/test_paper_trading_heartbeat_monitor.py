"""
Tests for paper-trading heartbeat freshness monitoring.

No broker connection is used.
No real order is placed.
"""

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

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


def make_health_snapshot():
    return {
        "health_status": "HEALTHY",
        "paper_trading_only": True,
        "real_order_execution": False,
        "total_failures": 0,
    }


def make_heartbeat(
    tmp_path,
    heartbeat_time,
):
    return (
        PaperTradingRuntimeHeartbeat(
            tmp_path / "heartbeat.json",
            clock=lambda: heartbeat_time,
        )
    )


def test_default_max_age_is_configured():
    monitor = (
        PaperTradingHeartbeatMonitor()
    )

    assert (
        monitor.max_age_seconds
        == 180.0
    )


def test_max_age_must_be_numeric():
    with pytest.raises(
        ValueError,
        match="max_age_seconds must be numeric",
    ):
        PaperTradingHeartbeatMonitor(
            max_age_seconds="invalid"
        )


def test_max_age_must_be_positive():
    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        PaperTradingHeartbeatMonitor(
            max_age_seconds=0
        )


def test_clock_must_be_callable():
    with pytest.raises(
        ValueError,
        match="clock must be callable",
    ):
        PaperTradingHeartbeatMonitor(
            clock="invalid"
        )


def test_missing_heartbeat_is_reported(
    tmp_path,
):
    heartbeat = (
        PaperTradingRuntimeHeartbeat(
            tmp_path / "missing.json"
        )
    )

    monitor = (
        PaperTradingHeartbeatMonitor(
            heartbeat,
            clock=lambda: NOW,
        )
    )

    result = monitor.check()

    assert result["success"] is True
    assert result["status"] == "MISSING"
    assert result["heartbeat_exists"] is False
    assert result["fresh"] is False
    assert result["stale"] is False
    assert result["age_seconds"] is None


def test_recent_heartbeat_is_fresh(
    tmp_path,
):
    heartbeat_time = (
        NOW
        - timedelta(
            seconds=60
        )
    )

    heartbeat = make_heartbeat(
        tmp_path,
        heartbeat_time,
    )

    heartbeat.write(
        make_health_snapshot()
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
    assert result["stale"] is False
    assert result["age_seconds"] == 60.0


def test_old_heartbeat_is_stale(
    tmp_path,
):
    heartbeat_time = (
        NOW
        - timedelta(
            seconds=300
        )
    )

    heartbeat = make_heartbeat(
        tmp_path,
        heartbeat_time,
    )

    heartbeat.write(
        make_health_snapshot()
    )

    monitor = (
        PaperTradingHeartbeatMonitor(
            heartbeat,
            max_age_seconds=180,
            clock=lambda: NOW,
        )
    )

    result = monitor.check()

    assert result["status"] == "STALE"
    assert result["fresh"] is False
    assert result["stale"] is True
    assert result["age_seconds"] == 300.0


def test_exact_age_limit_is_fresh(
    tmp_path,
):
    heartbeat_time = (
        NOW
        - timedelta(
            seconds=180
        )
    )

    heartbeat = make_heartbeat(
        tmp_path,
        heartbeat_time,
    )

    heartbeat.write(
        make_health_snapshot()
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


def test_health_snapshot_is_returned(
    tmp_path,
):
    heartbeat = make_heartbeat(
        tmp_path,
        NOW,
    )

    heartbeat.write(
        make_health_snapshot()
    )

    monitor = (
        PaperTradingHeartbeatMonitor(
            heartbeat,
            clock=lambda: NOW,
        )
    )

    result = monitor.check()

    assert (
        result["health_snapshot"][
            "health_status"
        ]
        == "HEALTHY"
    )


def test_future_timestamp_does_not_create_negative_age(
    tmp_path,
):
    heartbeat_time = (
        NOW
        + timedelta(
            seconds=30
        )
    )

    heartbeat = make_heartbeat(
        tmp_path,
        heartbeat_time,
    )

    heartbeat.write(
        make_health_snapshot()
    )

    monitor = (
        PaperTradingHeartbeatMonitor(
            heartbeat,
            clock=lambda: NOW,
        )
    )

    result = monitor.check()

    assert result["age_seconds"] == 0.0
    assert result["fresh"] is True


def test_get_status_is_alias_for_check(
    tmp_path,
):
    heartbeat = make_heartbeat(
        tmp_path,
        NOW,
    )

    heartbeat.write(
        make_health_snapshot()
    )

    monitor = (
        PaperTradingHeartbeatMonitor(
            heartbeat,
            clock=lambda: NOW,
        )
    )

    result = monitor.get_status()

    assert result["status"] == "FRESH"


def test_clock_must_return_datetime(
    tmp_path,
):
    heartbeat = make_heartbeat(
        tmp_path,
        NOW,
    )

    heartbeat.write(
        make_health_snapshot()
    )

    monitor = (
        PaperTradingHeartbeatMonitor(
            heartbeat,
            clock=lambda: "invalid",
        )
    )

    with pytest.raises(
        ValueError,
        match="clock must return a datetime",
    ):
        monitor.check()