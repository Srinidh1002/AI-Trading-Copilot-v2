"""
Continuous Paper Trading Entry Point.

Coordinates:

PaperTradingRecoveryManager
    -> recover persisted paper trades

ContinuousPaperTradingRuntime
    -> PaperTradingRuntimeAdapter
        -> live_option_decision_nifty.py
        -> monitor_paper_positions.py

PaperTradingRuntimeHealth
    -> reports final runtime operational health

Startup order:

1. Recover persisted paper trades.
2. Start opportunity cycle.
3. Start monitoring cycle.
4. Continue at configured interval.
5. Report final runtime health when stopped.

IMPORTANT:
- PAPER TRADING ONLY.
- NO REAL ORDER PLACEMENT.
- Existing standalone scripts run in isolated subprocesses.
- Recovery failure is fail-closed in the real continuous runtime.
"""

import inspect
import os
from pathlib import Path

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
from services.paper_trading_runtime_adapter import (
    PaperTradingRuntimeAdapter,
)
from services.paper_trading_runtime_health import (
    PaperTradingRuntimeHealth,
)


DEFAULT_INTERVAL_SECONDS = 60.0
DEFAULT_TIMEOUT_SECONDS = 300.0


def _read_positive_float(
    name,
    default,
):
    value = os.getenv(
        name
    )

    if value is None:
        return float(
            default
        )

    try:
        result = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            f"{name} must be numeric."
        ) from exc

    if result <= 0:
        raise ValueError(
            f"{name} must be greater than zero."
        )

    return result


def get_runtime_config():
    return {
        "interval_seconds": (
            _read_positive_float(
                "PAPER_TRADING_INTERVAL_SECONDS",
                DEFAULT_INTERVAL_SECONDS,
            )
        ),
        "timeout_seconds": (
            _read_positive_float(
                "PAPER_TRADING_SCRIPT_TIMEOUT_SECONDS",
                DEFAULT_TIMEOUT_SECONDS,
            )
        ),
    }


def print_header(
    config,
):
    print(
        "\n================================"
    )
    print(
        "AI TRADING COPILOT"
    )
    print(
        "CONTINUOUS PAPER TRADING RUNTIME"
    )
    print(
        "================================"
    )

    print(
        "\nMode: PAPER TRADING ONLY"
    )

    print(
        "Startup Recovery: ENABLED"
    )

    print(
        "Runtime Health Reporting: ENABLED"
    )

    print(
        "Cycle Interval:",
        config[
            "interval_seconds"
        ],
        "seconds",
    )

    print(
        "Script Timeout:",
        config[
            "timeout_seconds"
        ],
        "seconds",
    )

    print(
        "Real Order Execution: DISABLED"
    )

    print(
        "\nPress Ctrl+C to stop safely."
    )


def _print_subprocess_output(
    name,
    result,
):
    if not isinstance(
        result,
        dict,
    ):
        print(
            f"\n{name}: Invalid result"
        )
        return

    print(
        f"\n{name} STATUS:",
        result.get(
            "status"
        ),
    )

    stdout = (
        result.get(
            "stdout"
        )
        or ""
    ).strip()

    stderr = (
        result.get(
            "stderr"
        )
        or ""
    ).strip()

    if stdout:
        print(
            f"\n----- {name} OUTPUT -----"
        )
        print(
            stdout
        )

    if stderr:
        print(
            f"\n----- {name} STDERR -----"
        )
        print(
            stderr
        )


def create_cycle_callable(
    cycle_function,
    cycle_name,
):
    """
    Wrap an adapter subprocess cycle.

    Non-zero exits, timeouts, and execution failures become
    exceptions so ContinuousPaperTradingRuntime records them
    as operation failures.
    """

    if not callable(
        cycle_function
    ):
        raise ValueError(
            "cycle_function must be callable."
        )

    def cycle():
        result = (
            cycle_function()
        )

        if not isinstance(
            result,
            dict,
        ):
            raise RuntimeError(
                f"{cycle_name} returned invalid data."
            )

        _print_subprocess_output(
            cycle_name,
            result,
        )

        if not result.get(
            "success",
            False,
        ):
            error = (
                result.get(
                    "error"
                )
                or (
                    f"{cycle_name} cycle failed."
                )
            )

            raise RuntimeError(
                error
            )

        return result

    return cycle


def create_recovery_operation(
    *,
    repository_factory=PaperTradeRepository,
    engine_factory=PaperTradingEngine,
    recovery_manager_factory=(
        PaperTradingRecoveryManager
    ),
):
    """
    Build the startup paper-trade recovery operation.

    The repository and engine are reconstructed so persisted
    paper trades can be recovered before runtime cycle 1.
    """

    repository = (
        repository_factory()
    )

    engine = (
        engine_factory(
            repository=repository,
            persist_state=True,
        )
    )

    recovery_manager = (
        recovery_manager_factory(
            engine,
            include_closed=True,
        )
    )

    return (
        recovery_manager.recover
    )


def _runtime_supports_startup_operation(
    runtime_factory,
):
    """
    Detect whether a runtime factory accepts startup_operation.

    This preserves compatibility with older test/custom runtime
    factories while enabling startup recovery in the real runtime.
    """

    try:
        signature = (
            inspect.signature(
                runtime_factory
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        return True

    parameters = (
        signature.parameters
    )

    if (
        "startup_operation"
        in parameters
    ):
        return True

    return any(
        parameter.kind
        == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )


def build_runtime(
    *,
    config=None,
    adapter_factory=PaperTradingRuntimeAdapter,
    runtime_factory=ContinuousPaperTradingRuntime,
    repository_factory=PaperTradeRepository,
    engine_factory=PaperTradingEngine,
    recovery_manager_factory=(
        PaperTradingRecoveryManager
    ),
    working_directory=None,
):
    if config is None:
        config = (
            get_runtime_config()
        )

    if working_directory is None:
        working_directory = (
            Path(__file__)
            .resolve()
            .parent
        )

    adapter = (
        adapter_factory(
            opportunity_script=(
                "live_option_decision_nifty.py"
            ),
            monitoring_script=(
                "monitor_paper_positions.py"
            ),
            working_directory=(
                working_directory
            ),
            timeout_seconds=(
                config[
                    "timeout_seconds"
                ]
            ),
        )
    )

    opportunity_cycle = (
        create_cycle_callable(
            adapter.run_opportunity_cycle,
            "OPPORTUNITY",
        )
    )

    monitoring_cycle = (
        create_cycle_callable(
            adapter.run_monitoring_cycle,
            "MONITORING",
        )
    )

    runtime_kwargs = {
        "opportunity_cycle": (
            opportunity_cycle
        ),
        "monitoring_cycle": (
            monitoring_cycle
        ),
        "interval_seconds": (
            config[
                "interval_seconds"
            ]
        ),
    }

    if (
        _runtime_supports_startup_operation(
            runtime_factory
        )
    ):
        startup_operation = (
            create_recovery_operation(
                repository_factory=(
                    repository_factory
                ),
                engine_factory=(
                    engine_factory
                ),
                recovery_manager_factory=(
                    recovery_manager_factory
                ),
            )
        )

        runtime_kwargs[
            "startup_operation"
        ] = startup_operation

    runtime = (
        runtime_factory(
            **runtime_kwargs
        )
    )

    return (
        runtime,
        adapter,
    )


def create_health_snapshot(
    runtime,
):
    """
    Build a final read-only runtime health snapshot.

    Compatibility behavior:
    custom or legacy runtimes without get_stats() return None
    instead of breaking the entry point.
    """

    get_stats = getattr(
        runtime,
        "get_stats",
        None,
    )

    if not callable(
        get_stats
    ):
        return None

    health = (
        PaperTradingRuntimeHealth(
            runtime
        )
    )

    return (
        health.snapshot()
    )


def print_runtime_health(
    health_snapshot,
):
    """
    Print the final runtime health report.
    """

    if not isinstance(
        health_snapshot,
        dict,
    ):
        return

    print(
        "\n================================"
    )
    print(
        "RUNTIME HEALTH"
    )
    print(
        "================================"
    )

    print(
        "Health Status:",
        health_snapshot.get(
            "health_status",
            "UNKNOWN",
        ),
    )

    print(
        "Paper Trading Only:",
        health_snapshot.get(
            "paper_trading_only",
            True,
        ),
    )

    print(
        "Real Order Execution:",
        health_snapshot.get(
            "real_order_execution",
            False,
        ),
    )

    print(
        "Total Failures:",
        health_snapshot.get(
            "total_failures",
            0,
        ),
    )

    startup = (
        health_snapshot.get(
            "startup"
        )
        or {}
    )

    print(
        "Startup Health:",
        startup.get(
            "status",
            "NOT_REPORTED",
        ),
    )


def print_final_stats(
    stats,
    health_snapshot=None,
):
    print(
        "\n================================"
    )
    print(
        "RUNTIME STOPPED"
    )
    print(
        "================================"
    )

    print(
        "Startup Status:",
        stats.get(
            "startup_status",
            "NOT_REPORTED",
        ),
    )

    startup_result = (
        stats.get(
            "startup_result"
        )
    )

    if isinstance(
        startup_result,
        dict,
    ):
        print(
            "Recovered Trades:",
            startup_result.get(
                "recovered_count",
                0,
            ),
        )

        print(
            "Recovered Open Trades:",
            startup_result.get(
                "open_count",
                0,
            ),
        )

        print(
            "Recovered Closed Trades:",
            startup_result.get(
                "closed_count",
                0,
            ),
        )

    startup_error = (
        stats.get(
            "startup_error"
        )
    )

    if startup_error:
        print(
            "Startup Error:",
            startup_error,
        )

    print(
        "Cycles Started:",
        stats.get(
            "cycles_started",
            0,
        ),
    )

    print(
        "Cycles Completed:",
        stats.get(
            "cycles_completed",
            0,
        ),
    )

    print(
        "Cycles With Errors:",
        stats.get(
            "cycles_with_errors",
            0,
        ),
    )

    print(
        "Opportunity Successes:",
        stats.get(
            "opportunity_successes",
            0,
        ),
    )

    print(
        "Opportunity Failures:",
        stats.get(
            "opportunity_failures",
            0,
        ),
    )

    print(
        "Monitoring Successes:",
        stats.get(
            "monitoring_successes",
            0,
        ),
    )

    print(
        "Monitoring Failures:",
        stats.get(
            "monitoring_failures",
            0,
        ),
    )

    print(
        "Interrupted:",
        stats.get(
            "interrupted",
            False,
        ),
    )

    print_runtime_health(
        health_snapshot
    )

    print(
        "\nPAPER TRADING ONLY"
    )

    print(
        "NO REAL ORDER WAS PLACED"
    )


def main(
    *,
    max_cycles=None,
    config=None,
    adapter_factory=PaperTradingRuntimeAdapter,
    runtime_factory=ContinuousPaperTradingRuntime,
    repository_factory=PaperTradeRepository,
    engine_factory=PaperTradingEngine,
    recovery_manager_factory=(
        PaperTradingRecoveryManager
    ),
    working_directory=None,
):
    try:
        if config is None:
            config = (
                get_runtime_config()
            )

        print_header(
            config
        )

        runtime, _ = (
            build_runtime(
                config=config,
                adapter_factory=(
                    adapter_factory
                ),
                runtime_factory=(
                    runtime_factory
                ),
                repository_factory=(
                    repository_factory
                ),
                engine_factory=(
                    engine_factory
                ),
                recovery_manager_factory=(
                    recovery_manager_factory
                ),
                working_directory=(
                    working_directory
                ),
            )
        )

        stats = (
            runtime.run(
                max_cycles=max_cycles
            )
        )

        health_snapshot = (
            create_health_snapshot(
                runtime
            )
        )

        print_final_stats(
            stats,
            health_snapshot=(
                health_snapshot
            ),
        )

        return 0

    except KeyboardInterrupt:
        print(
            "\nShutdown requested."
        )

        print(
            "PAPER TRADING ONLY"
        )

        print(
            "NO REAL ORDER WAS PLACED"
        )

        return 0

    except Exception as exc:
        print(
            "\n================================"
        )
        print(
            "RUNTIME ERROR"
        )
        print(
            "================================"
        )

        print(
            "Error:",
            str(
                exc
            ),
        )

        print(
            "\nPAPER TRADING ONLY"
        )

        print(
            "NO REAL ORDER WAS PLACED"
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(
        main()
    )