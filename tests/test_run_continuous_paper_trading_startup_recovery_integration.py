"""
Integration tests for continuous paper-trading startup recovery.

Verifies that persisted paper trades are recovered before
the first opportunity and monitoring cycle begins.

No broker connection is used.
No real order is placed.
"""

from services.continuous_paper_trading_runtime import (
    ContinuousPaperTradingRuntime,
)
from services.paper_trade_repository import (
    PaperTradeRepository,
)
from services.paper_trading_engine import (
    PaperTradingEngine,
)
from services.paper_trading_recovery_manager import (
    PaperTradingRecoveryManager,
)


def make_pipeline_result():
    return {
        "decision": "TRADE_ALLOWED",
        "direction": "BULLISH",
        "contract": {
            "selected": True,
            "symbol": "NIFTY_TEST_CE",
            "option_type": "CE",
            "strike": 25000.0,
            "expiry": "2026-07-30",
            "premium": 100.0,
            "lot_size": 75,
        },
        "trade_plan": {
            "allowed": True,
            "levels": {
                "option_entry_price": 100.0,
                "option_stop_loss": 90.0,
                "option_target": 120.0,
            },
            "risk": {
                "allowed": True,
                "lots": 1,
                "quantity": 75,
                "required_capital": 7500.0,
                "estimated_maximum_loss": 750.0,
            },
        },
    }


def make_engine(
    file_path,
):
    repository = (
        PaperTradeRepository(
            file_path=file_path
        )
    )

    return PaperTradingEngine(
        repository=repository,
        persist_state=True,
    )


def test_startup_recovery_runs_before_first_cycle(
    tmp_path,
):
    file_path = (
        tmp_path
        / "paper_trades.json"
    )

    engine_before = (
        make_engine(
            file_path
        )
    )

    engine_before.open_trade(
        make_pipeline_result(),
        underlying="NIFTY",
        exchange="NFO",
        symboltoken="123456",
        trade_id="startup-recovery-1",
    )

    engine_after = (
        make_engine(
            file_path
        )
    )

    recovery_manager = (
        PaperTradingRecoveryManager(
            engine_after,
            include_closed=True,
        )
    )

    events = []

    def startup_operation():
        events.append(
            "STARTUP"
        )

        result = (
            recovery_manager.recover()
        )

        events.append(
            "RECOVERY_COMPLETE"
        )

        return result

    def opportunity_cycle():
        events.append(
            "OPPORTUNITY"
        )

        return {
            "success": True,
        }

    def monitoring_cycle():
        events.append(
            "MONITORING"
        )

        return {
            "success": True,
        }

    runtime = (
        ContinuousPaperTradingRuntime(
            opportunity_cycle=(
                opportunity_cycle
            ),
            monitoring_cycle=(
                monitoring_cycle
            ),
            startup_operation=(
                startup_operation
            ),
            interval_seconds=60.0,
        )
    )

    stats = (
        runtime.run(
            max_cycles=1
        )
    )

    assert events == [
        "STARTUP",
        "RECOVERY_COMPLETE",
        "OPPORTUNITY",
        "MONITORING",
    ]

    assert (
        stats["startup_status"]
        == "COMPLETED"
    )

    assert (
        stats["startup_result"][
            "success"
        ]
        is True
    )

    assert (
        stats["startup_result"][
            "recovered_count"
        ]
        == 1
    )

    assert (
        stats["startup_result"][
            "open_count"
        ]
        == 1
    )

    assert (
        stats["cycles_started"]
        == 1
    )

    assert (
        stats["cycles_completed"]
        == 1
    )


def test_startup_recovery_failure_blocks_all_cycles():
    events = []

    def startup_operation():
        events.append(
            "STARTUP"
        )

        return {
            "success": False,
            "status": "FAILED",
            "error": (
                "Simulated recovery failure."
            ),
        }

    def opportunity_cycle():
        events.append(
            "OPPORTUNITY"
        )

    def monitoring_cycle():
        events.append(
            "MONITORING"
        )

    runtime = (
        ContinuousPaperTradingRuntime(
            opportunity_cycle=(
                opportunity_cycle
            ),
            monitoring_cycle=(
                monitoring_cycle
            ),
            startup_operation=(
                startup_operation
            ),
            interval_seconds=60.0,
        )
    )

    stats = (
        runtime.run(
            max_cycles=1
        )
    )

    assert events == [
        "STARTUP",
    ]

    assert (
        stats["startup_status"]
        == "FAILED"
    )

    assert (
        stats["cycles_started"]
        == 0
    )

    assert (
        stats["cycles_completed"]
        == 0
    )


def test_empty_recovery_allows_first_cycle(
    tmp_path,
):
    file_path = (
        tmp_path
        / "paper_trades.json"
    )

    engine = (
        make_engine(
            file_path
        )
    )

    recovery_manager = (
        PaperTradingRecoveryManager(
            engine,
            include_closed=True,
        )
    )

    events = []

    def startup_operation():
        events.append(
            "STARTUP"
        )

        return (
            recovery_manager.recover()
        )

    def opportunity_cycle():
        events.append(
            "OPPORTUNITY"
        )

        return {
            "success": True,
        }

    def monitoring_cycle():
        events.append(
            "MONITORING"
        )

        return {
            "success": True,
        }

    runtime = (
        ContinuousPaperTradingRuntime(
            opportunity_cycle=(
                opportunity_cycle
            ),
            monitoring_cycle=(
                monitoring_cycle
            ),
            startup_operation=(
                startup_operation
            ),
            interval_seconds=60.0,
        )
    )

    stats = (
        runtime.run(
            max_cycles=1
        )
    )

    assert events == [
        "STARTUP",
        "OPPORTUNITY",
        "MONITORING",
    ]

    assert (
        stats["startup_status"]
        == "COMPLETED"
    )

    assert (
        stats["startup_result"][
            "status"
        ]
        == "EMPTY"
    )

    assert (
        stats["startup_result"][
            "recovered_count"
        ]
        == 0
    )

    assert (
        stats["cycles_completed"]
        == 1
    )