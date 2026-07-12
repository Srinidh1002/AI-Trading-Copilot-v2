"""
Tests for paper-trading runtime heartbeat persistence.

No broker connection is used.
No real order is placed.
"""

import json
from datetime import datetime, timezone

import pytest

from services.paper_trading_runtime_heartbeat import (
    PaperTradingRuntimeHeartbeat,
)


FIXED_TIME = datetime(
    2026,
    7,
    13,
    10,
    30,
    0,
    tzinfo=timezone.utc,
)


def fixed_clock():
    return FIXED_TIME


def make_health_snapshot():
    return {
        "health_status": "HEALTHY",
        "paper_trading_only": True,
        "real_order_execution": False,
        "running": True,
        "interrupted": False,
        "startup": {
            "status": "COMPLETED",
            "result": {
                "success": True,
                "recovered_count": 1,
            },
            "error": None,
        },
        "cycles": {
            "started": 2,
            "completed": 2,
            "with_errors": 0,
        },
        "operations": {
            "opportunity_successes": 2,
            "opportunity_failures": 0,
            "monitoring_successes": 2,
            "monitoring_failures": 0,
        },
        "total_failures": 0,
    }


def test_default_file_path_is_configured():
    heartbeat = (
        PaperTradingRuntimeHeartbeat()
    )

    assert (
        heartbeat.file_path
        == heartbeat.DEFAULT_FILE_PATH
    )


def test_clock_must_be_callable(
    tmp_path,
):
    with pytest.raises(
        ValueError,
        match="clock must be callable",
    ):
        PaperTradingRuntimeHeartbeat(
            tmp_path / "heartbeat.json",
            clock="invalid",
        )


def test_write_requires_dictionary(
    tmp_path,
):
    heartbeat = (
        PaperTradingRuntimeHeartbeat(
            tmp_path / "heartbeat.json",
            clock=fixed_clock,
        )
    )

    with pytest.raises(
        ValueError,
        match="health_snapshot must be a dictionary",
    ):
        heartbeat.write(
            None
        )


def test_write_creates_heartbeat_file(
    tmp_path,
):
    file_path = (
        tmp_path
        / "heartbeat.json"
    )

    heartbeat = (
        PaperTradingRuntimeHeartbeat(
            file_path,
            clock=fixed_clock,
        )
    )

    result = heartbeat.write(
        make_health_snapshot()
    )

    assert file_path.exists()

    assert (
        result["heartbeat_at"]
        == FIXED_TIME.isoformat()
    )

    assert (
        result["health_snapshot"][
            "health_status"
        ]
        == "HEALTHY"
    )


def test_write_creates_parent_directories(
    tmp_path,
):
    file_path = (
        tmp_path
        / "nested"
        / "runtime"
        / "heartbeat.json"
    )

    heartbeat = (
        PaperTradingRuntimeHeartbeat(
            file_path,
            clock=fixed_clock,
        )
    )

    heartbeat.write(
        make_health_snapshot()
    )

    assert file_path.exists()


def test_read_returns_persisted_heartbeat(
    tmp_path,
):
    file_path = (
        tmp_path
        / "heartbeat.json"
    )

    heartbeat = (
        PaperTradingRuntimeHeartbeat(
            file_path,
            clock=fixed_clock,
        )
    )

    written = heartbeat.write(
        make_health_snapshot()
    )

    loaded = heartbeat.read()

    assert loaded == written


def test_read_returns_none_when_file_missing(
    tmp_path,
):
    heartbeat = (
        PaperTradingRuntimeHeartbeat(
            tmp_path / "missing.json"
        )
    )

    assert heartbeat.read() is None


def test_exists_reports_file_state(
    tmp_path,
):
    file_path = (
        tmp_path
        / "heartbeat.json"
    )

    heartbeat = (
        PaperTradingRuntimeHeartbeat(
            file_path,
            clock=fixed_clock,
        )
    )

    assert heartbeat.exists() is False

    heartbeat.write(
        make_health_snapshot()
    )

    assert heartbeat.exists() is True


def test_write_does_not_mutate_original_snapshot(
    tmp_path,
):
    snapshot = (
        make_health_snapshot()
    )

    heartbeat = (
        PaperTradingRuntimeHeartbeat(
            tmp_path / "heartbeat.json",
            clock=fixed_clock,
        )
    )

    result = heartbeat.write(
        snapshot
    )

    result[
        "health_snapshot"
    ][
        "health_status"
    ] = "FAILED"

    assert (
        snapshot["health_status"]
        == "HEALTHY"
    )


def test_read_returns_independent_dictionary(
    tmp_path,
):
    heartbeat = (
        PaperTradingRuntimeHeartbeat(
            tmp_path / "heartbeat.json",
            clock=fixed_clock,
        )
    )

    heartbeat.write(
        make_health_snapshot()
    )

    first = heartbeat.read()

    first[
        "health_snapshot"
    ][
        "health_status"
    ] = "FAILED"

    second = heartbeat.read()

    assert (
        second["health_snapshot"][
            "health_status"
        ]
        == "HEALTHY"
    )


def test_naive_datetime_is_treated_as_utc(
    tmp_path,
):
    naive_time = datetime(
        2026,
        7,
        13,
        10,
        30,
        0,
    )

    heartbeat = (
        PaperTradingRuntimeHeartbeat(
            tmp_path / "heartbeat.json",
            clock=lambda: naive_time,
        )
    )

    result = heartbeat.write(
        make_health_snapshot()
    )

    assert (
        result["heartbeat_at"]
        == naive_time.replace(
            tzinfo=timezone.utc
        ).isoformat()
    )


def test_clock_must_return_datetime(
    tmp_path,
):
    heartbeat = (
        PaperTradingRuntimeHeartbeat(
            tmp_path / "heartbeat.json",
            clock=lambda: "invalid",
        )
    )

    with pytest.raises(
        ValueError,
        match="clock must return a datetime",
    ):
        heartbeat.write(
            make_health_snapshot()
        )


def test_invalid_json_raises_runtime_error(
    tmp_path,
):
    file_path = (
        tmp_path
        / "heartbeat.json"
    )

    file_path.write_text(
        "{invalid json",
        encoding="utf-8",
    )

    heartbeat = (
        PaperTradingRuntimeHeartbeat(
            file_path
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to read runtime heartbeat",
    ):
        heartbeat.read()


def test_non_dictionary_payload_is_rejected(
    tmp_path,
):
    file_path = (
        tmp_path
        / "heartbeat.json"
    )

    file_path.write_text(
        json.dumps(
            [
                "invalid"
            ]
        ),
        encoding="utf-8",
    )

    heartbeat = (
        PaperTradingRuntimeHeartbeat(
            file_path
        )
    )

    with pytest.raises(
        RuntimeError,
        match="must contain a dictionary",
    ):
        heartbeat.read()


def test_invalid_timestamp_is_rejected(
    tmp_path,
):
    file_path = (
        tmp_path
        / "heartbeat.json"
    )

    file_path.write_text(
        json.dumps(
            {
                "heartbeat_at": None,
                "health_snapshot": {},
            }
        ),
        encoding="utf-8",
    )

    heartbeat = (
        PaperTradingRuntimeHeartbeat(
            file_path
        )
    )

    with pytest.raises(
        RuntimeError,
        match="timestamp is invalid",
    ):
        heartbeat.read()


def test_invalid_health_snapshot_is_rejected(
    tmp_path,
):
    file_path = (
        tmp_path
        / "heartbeat.json"
    )

    file_path.write_text(
        json.dumps(
            {
                "heartbeat_at": (
                    FIXED_TIME.isoformat()
                ),
                "health_snapshot": None,
            }
        ),
        encoding="utf-8",
    )

    heartbeat = (
        PaperTradingRuntimeHeartbeat(
            file_path
        )
    )

    with pytest.raises(
        RuntimeError,
        match="health snapshot is invalid",
    ):
        heartbeat.read()


def test_second_write_replaces_previous_heartbeat(
    tmp_path,
):
    file_path = (
        tmp_path
        / "heartbeat.json"
    )

    heartbeat = (
        PaperTradingRuntimeHeartbeat(
            file_path,
            clock=fixed_clock,
        )
    )

    first_snapshot = (
        make_health_snapshot()
    )

    heartbeat.write(
        first_snapshot
    )

    second_snapshot = (
        make_health_snapshot()
    )

    second_snapshot[
        "health_status"
    ] = "DEGRADED"

    heartbeat.write(
        second_snapshot
    )

    loaded = heartbeat.read()

    assert (
        loaded["health_snapshot"][
            "health_status"
        ]
        == "DEGRADED"
    )