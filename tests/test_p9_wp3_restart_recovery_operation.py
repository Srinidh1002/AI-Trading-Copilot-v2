from datetime import datetime, timezone
from types import SimpleNamespace

from services.paper_orchestration.restart_recovery_operation import (
    RestartRecoveryOperation,
    RestartRecoveryTargetV1,
)


NOW = datetime(2026, 1, 8, 9, 30, tzinfo=timezone.utc)


def clock():
    return NOW


def test_restart_recovery_succeeds_only_when_all_targets_recover():
    operation = RestartRecoveryOperation(
        targets=(
            RestartRecoveryTargetV1(
                target_type="P7_TRADE",
                target_id="trade-1",
                recovery_authority=lambda target_id, now: (
                    SimpleNamespace(status="RECOVERED")
                ),
            ),
            RestartRecoveryTargetV1(
                target_type="P8_PORTFOLIO",
                target_id="portfolio-1",
                recovery_authority=lambda target_id, now: (
                    SimpleNamespace(status="RECOVERED")
                ),
            ),
        ),
        clock=clock,
    )

    result = operation()

    assert result["success"] is True
    assert result["target_count"] == 2
    assert all(item["success"] for item in result["results"])


def test_restart_recovery_fails_closed_for_non_recovered_target():
    operation = RestartRecoveryOperation(
        targets=(
            RestartRecoveryTargetV1(
                target_type="P7_TRADE",
                target_id="trade-1",
                recovery_authority=lambda target_id, now: (
                    SimpleNamespace(status="NOT_FOUND")
                ),
            ),
        ),
        clock=clock,
    )

    result = operation()

    assert result["success"] is False
    assert result["results"][0]["status"] == "NOT_FOUND"


def test_restart_recovery_captures_authority_exception():
    operation = RestartRecoveryOperation(
        targets=(
            RestartRecoveryTargetV1(
                target_type="P8_PORTFOLIO",
                target_id="portfolio-1",
                recovery_authority=lambda target_id, now: (
                    (_ for _ in ()).throw(RuntimeError("corrupt"))
                ),
            ),
        ),
        clock=clock,
    )

    result = operation()

    assert result["success"] is False
    assert result["results"][0]["status"] == "ERROR"
    assert result["results"][0]["error"] == "corrupt"
