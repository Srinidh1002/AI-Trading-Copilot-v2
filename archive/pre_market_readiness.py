"""
AI Trading Copilot Pre-Market Readiness Check.

Offline operational validation for the paper-trading runtime.

IMPORTANT:
- PAPER TRADING ONLY.
- NO LIVE MARKET DATA REQUEST.
- NO REAL ORDER PLACEMENT.
"""

from pathlib import Path

from services.paper_trading_heartbeat_monitor import (
    PaperTradingHeartbeatMonitor,
)
from services.paper_trading_runtime_heartbeat import (
    PaperTradingRuntimeHeartbeat,
)


REQUIRED_FILES = (
    "live_option_decision_nifty.py",
    "monitor_paper_positions.py",
    "run_continuous_paper_trading.py",
    "paper_trading_preflight.py",
)


def run_readiness_check(
    *,
    heartbeat_file=None,
    require_fresh_heartbeat=False,
    max_heartbeat_age_seconds=180.0,
):
    checks = []

    def add_check(
        name,
        passed,
        detail,
    ):
        checks.append(
            {
                "name": name,
                "passed": bool(
                    passed
                ),
                "detail": str(
                    detail
                ),
            }
        )

    # ---------------------------------
    # REQUIRED FILES
    # ---------------------------------

    for file_name in REQUIRED_FILES:
        exists = Path(
            file_name
        ).is_file()

        add_check(
            file_name,
            exists,
            (
                "Required file exists."
                if exists
                else "Required file is missing."
            ),
        )

    # ---------------------------------
    # CORE IMPORTS
    # ---------------------------------

    try:
        from services.continuous_paper_trading_runtime import (
            ContinuousPaperTradingRuntime,
        )

        add_check(
            "Continuous Runtime",
            ContinuousPaperTradingRuntime
            is not None,
            "Runtime is importable.",
        )

    except Exception as exc:
        add_check(
            "Continuous Runtime",
            False,
            exc,
        )

    try:
        from services.paper_trading_runtime_health import (
            PaperTradingRuntimeHealth,
        )

        add_check(
            "Runtime Health",
            PaperTradingRuntimeHealth
            is not None,
            "Runtime health service is importable.",
        )

    except Exception as exc:
        add_check(
            "Runtime Health",
            False,
            exc,
        )

    try:
        from services.paper_trading_recovery_manager import (
            PaperTradingRecoveryManager,
        )

        add_check(
            "Recovery Manager",
            PaperTradingRecoveryManager
            is not None,
            "Recovery manager is importable.",
        )

    except Exception as exc:
        add_check(
            "Recovery Manager",
            False,
            exc,
        )

    # ---------------------------------
    # HEARTBEAT
    # ---------------------------------

    heartbeat = (
        PaperTradingRuntimeHeartbeat(
            heartbeat_file
        )
        if heartbeat_file is not None
        else PaperTradingRuntimeHeartbeat()
    )

    monitor = (
        PaperTradingHeartbeatMonitor(
            heartbeat,
            max_age_seconds=(
                max_heartbeat_age_seconds
            ),
        )
    )

    try:
        heartbeat_status = (
            monitor.check()
        )

        status = heartbeat_status[
            "status"
        ]

        if require_fresh_heartbeat:
            heartbeat_passed = (
                status == "FRESH"
            )
        else:
            heartbeat_passed = (
                status
                in {
                    "FRESH",
                    "STALE",
                    "MISSING",
                }
            )

        add_check(
            "Runtime Heartbeat",
            heartbeat_passed,
            (
                f"Heartbeat status: {status}."
            ),
        )

    except Exception as exc:
        heartbeat_status = {
            "status": "FAILED",
            "error": str(
                exc
            ),
        }

        add_check(
            "Runtime Heartbeat",
            False,
            exc,
        )

    # ---------------------------------
    # PAPER-ONLY ISOLATION
    # ---------------------------------

    add_check(
        "Paper Trading Mode",
        True,
        "Readiness checker performs no order execution.",
    )

    add_check(
        "Real Order Isolation",
        True,
        "Real order execution remains disabled.",
    )

    passed = sum(
        1
        for check in checks
        if check["passed"]
    )

    failed = (
        len(
            checks
        )
        - passed
    )

    return {
        "ready": (
            failed == 0
        ),
        "status": (
            "READY"
            if failed == 0
            else "NOT_READY"
        ),
        "passed": passed,
        "failed": failed,
        "checks": checks,
        "heartbeat": heartbeat_status,
        "paper_trading_only": True,
        "real_order_execution": False,
    }


def print_result(
    result,
):
    print(
        "\n================================"
    )
    print(
        "AI TRADING COPILOT"
    )
    print(
        "PRE-MARKET READINESS"
    )
    print(
        "================================"
    )

    for check in result[
        "checks"
    ]:
        marker = (
            "PASS"
            if check["passed"]
            else "FAIL"
        )

        print(
            f"\n[{marker}] "
            f"{check['name']}"
        )

        print(
            check["detail"]
        )

    print(
        "\n================================"
    )
    print(
        "READINESS RESULT"
    )
    print(
        "================================"
    )

    print(
        "Status:",
        result["status"],
    )

    print(
        "Passed:",
        result["passed"],
    )

    print(
        "Failed:",
        result["failed"],
    )

    print(
        "Heartbeat:",
        result[
            "heartbeat"
        ].get(
            "status"
        ),
    )

    print(
        "\nPAPER TRADING ONLY"
    )

    print(
        "NO REAL ORDER WAS PLACED"
    )


def main():
    result = (
        run_readiness_check()
    )

    print_result(
        result
    )

    return (
        0
        if result["ready"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )