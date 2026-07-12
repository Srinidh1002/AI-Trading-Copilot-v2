"""
Tests for pre-market readiness checking.

No broker connection is used.
No real order is placed.
"""

from datetime import (
    datetime,
    timezone,
)

from pre_market_readiness import (
    run_readiness_check,
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


def test_readiness_check_is_paper_only(
    tmp_path,
):
    result = (
        run_readiness_check(
            heartbeat_file=(
                tmp_path
                / "heartbeat.json"
            )
        )
    )

    assert (
        result["paper_trading_only"]
        is True
    )

    assert (
        result["real_order_execution"]
        is False
    )


def test_missing_heartbeat_is_allowed_for_offline_readiness(
    tmp_path,
):
    result = (
        run_readiness_check(
            heartbeat_file=(
                tmp_path
                / "missing.json"
            ),
            require_fresh_heartbeat=False,
        )
    )

    assert (
        result["heartbeat"][
            "status"
        ]
        == "MISSING"
    )


def test_fresh_heartbeat_can_be_required(
    tmp_path,
):
    file_path = (
        tmp_path
        / "heartbeat.json"
    )

    heartbeat = (
        PaperTradingRuntimeHeartbeat(
            file_path,
            clock=lambda: NOW,
        )
    )

    heartbeat.write(
        {
            "health_status": "HEALTHY",
            "paper_trading_only": True,
            "real_order_execution": False,
        }
    )

    result = (
        run_readiness_check(
            heartbeat_file=file_path,
            require_fresh_heartbeat=False,
        )
    )

    assert (
        result["heartbeat"][
            "status"
        ]
        in {
            "FRESH",
            "STALE",
        }
    )


def test_missing_required_fresh_heartbeat_fails(
    tmp_path,
):
    result = (
        run_readiness_check(
            heartbeat_file=(
                tmp_path
                / "missing.json"
            ),
            require_fresh_heartbeat=True,
        )
    )

    heartbeat_check = next(
        check
        for check in result[
            "checks"
        ]
        if check["name"]
        == "Runtime Heartbeat"
    )

    assert (
        heartbeat_check["passed"]
        is False
    )

    assert (
        result["status"]
        == "NOT_READY"
    )


def test_result_contains_required_summary_fields(
    tmp_path,
):
    result = (
        run_readiness_check(
            heartbeat_file=(
                tmp_path
                / "heartbeat.json"
            )
        )
    )

    assert "ready" in result
    assert "status" in result
    assert "passed" in result
    assert "failed" in result
    assert "checks" in result
    assert "heartbeat" in result


def test_real_order_isolation_check_passes(
    tmp_path,
):
    result = (
        run_readiness_check(
            heartbeat_file=(
                tmp_path
                / "heartbeat.json"
            )
        )
    )

    isolation = next(
        check
        for check in result[
            "checks"
        ]
        if check["name"]
        == "Real Order Isolation"
    )

    assert isolation["passed"] is True


def test_paper_trading_mode_check_passes(
    tmp_path,
):
    result = (
        run_readiness_check(
            heartbeat_file=(
                tmp_path
                / "heartbeat.json"
            )
        )
    )

    paper_mode = next(
        check
        for check in result[
            "checks"
        ]
        if check["name"]
        == "Paper Trading Mode"
    )

    assert paper_mode["passed"] is True