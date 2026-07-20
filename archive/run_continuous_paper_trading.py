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

PaperTradingRuntimeHeartbeat
    -> persists final runtime health status

Startup order:

1. Configure parent runtime output for UTF-8.
2. Recover persisted paper trades.
3. Start opportunity cycle.
4. Start monitoring cycle.
5. Continue at configured interval.
6. Report final runtime health when stopped.
7. Persist final runtime heartbeat.

IMPORTANT:
- PAPER TRADING ONLY.
- NO REAL ORDER PLACEMENT.
- Existing standalone scripts run in isolated subprocesses.
- Recovery failure is fail-closed in the real continuous runtime.
- Subprocess Unicode output must never break a runtime cycle.
"""

import inspect
import os
from pathlib import Path
import sys

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
from services.paper_trading_runtime_heartbeat import (
    PaperTradingRuntimeHeartbeat,
)


DEFAULT_INTERVAL_SECONDS = 60.0
DEFAULT_TIMEOUT_SECONDS = 300.0


def _configure_utf8_output():
    """
    Configure parent runtime output streams for UTF-8.

    PaperTradingRuntimeAdapter already captures child subprocess
    output as UTF-8. The parent runtime must also be able to
    safely reprint Unicode text such as the Indian rupee symbol
    on Windows.

    This configuration is best-effort and must never prevent the
    paper-trading runtime from starting.
    """

    for stream in (
        sys.stdout,
        sys.stderr,
    ):
        reconfigure = getattr(
            stream,
            "reconfigure",
            None,
        )

        if not callable(
            reconfigure
        ):
            continue

        try:
            reconfigure(
                encoding="utf-8",
                errors="replace",
            )

        except (
            OSError,
            ValueError,
            AttributeError,
        ):
            continue


def _safe_print_text(
    value,
    *,
    stream=None,
):
    """
    Print text without allowing console encoding failures to
    break a paper-trading runtime cycle.

    Unicode output is printed normally when supported.

    If the active output stream cannot encode a character, the
    text is converted using the stream encoding with replacement
    semantics.

    Printing diagnostics must never convert an otherwise
    successful market-analysis subprocess into an opportunity
    failure.
    """

    if stream is None:
        stream = sys.stdout

    text = str(
        value
    )

    try:
        print(
            text,
            file=stream,
        )

        return

    except UnicodeEncodeError:
        pass

    encoding = (
        getattr(
            stream,
            "encoding",
            None,
        )
        or "utf-8"
    )

    try:
        safe_text = (
            text
            .encode(
                encoding,
                errors="replace",
            )
            .decode(
                encoding,
                errors="replace",
            )
        )

    except (
        LookupError,
        UnicodeError,
    ):
        safe_text = (
            text
            .encode(
                "ascii",
                errors="replace",
            )
            .decode(
                "ascii",
                errors="replace",
            )
        )

    try:
        print(
            safe_text,
            file=stream,
        )

    except UnicodeEncodeError:
        fallback_text = (
            safe_text
            .encode(
                "ascii",
                errors="replace",
            )
            .decode(
                "ascii",
                errors="replace",
            )
        )

        print(
            fallback_text,
            file=stream,
        )


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
    _safe_print_text(
        "\n================================"
    )

    _safe_print_text(
        "AI TRADING COPILOT"
    )

    _safe_print_text(
        "CONTINUOUS PAPER TRADING RUNTIME"
    )

    _safe_print_text(
        "================================"
    )

    _safe_print_text(
        "\nMode: PAPER TRADING ONLY"
    )

    _safe_print_text(
        "Startup Recovery: ENABLED"
    )

    _safe_print_text(
        "Runtime Health Reporting: ENABLED"
    )

    _safe_print_text(
        "Runtime Heartbeat Persistence: ENABLED"
    )

    _safe_print_text(
        (
            "Cycle Interval: "
            f"{config['interval_seconds']} seconds"
        )
    )

    _safe_print_text(
        (
            "Script Timeout: "
            f"{config['timeout_seconds']} seconds"
        )
    )

    _safe_print_text(
        "Real Order Execution: DISABLED"
    )

    _safe_print_text(
        "\nPress Ctrl+C to stop safely."
    )


def _print_subprocess_output(
    name,
    result,
):
    """
    Print one subprocess cycle result safely.

    Captured subprocess output may contain Unicode characters.
    Output rendering must never affect the success or failure
    status of the underlying market-analysis operation.
    """

    if not isinstance(
        result,
        dict,
    ):
        _safe_print_text(
            f"\n{name}: Invalid result"
        )

        return

    _safe_print_text(
        (
            f"\n{name} STATUS: "
            f"{result.get('status')}"
        )
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
        _safe_print_text(
            f"\n----- {name} OUTPUT -----"
        )

        _safe_print_text(
            stdout
        )

    if stderr:
        _safe_print_text(
            f"\n----- {name} STDERR -----"
        )

        _safe_print_text(
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

    Console rendering failures are isolated from subprocess
    operation status.
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


def persist_runtime_heartbeat(
    health_snapshot,
    *,
    heartbeat_factory=PaperTradingRuntimeHeartbeat,
):
    """
    Persist the final runtime health snapshot.

    Returns None when no health snapshot is available.
    """

    if health_snapshot is None:
        return None

    heartbeat = (
        heartbeat_factory()
    )

    return (
        heartbeat.write(
            health_snapshot
        )
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

    _safe_print_text(
        "\n================================"
    )

    _safe_print_text(
        "RUNTIME HEALTH"
    )

    _safe_print_text(
        "================================"
    )

    _safe_print_text(
        (
            "Health Status: "
            f"{health_snapshot.get('health_status', 'UNKNOWN')}"
        )
    )

    _safe_print_text(
        (
            "Paper Trading Only: "
            f"{health_snapshot.get('paper_trading_only', True)}"
        )
    )

    _safe_print_text(
        (
            "Real Order Execution: "
            f"{health_snapshot.get('real_order_execution', False)}"
        )
    )

    _safe_print_text(
        (
            "Total Failures: "
            f"{health_snapshot.get('total_failures', 0)}"
        )
    )

    startup = (
        health_snapshot.get(
            "startup"
        )
        or {}
    )

    _safe_print_text(
        (
            "Startup Health: "
            f"{startup.get('status', 'NOT_REPORTED')}"
        )
    )


def print_final_stats(
    stats,
    health_snapshot=None,
):
    _safe_print_text(
        "\n================================"
    )

    _safe_print_text(
        "RUNTIME STOPPED"
    )

    _safe_print_text(
        "================================"
    )

    _safe_print_text(
        (
            "Startup Status: "
            f"{stats.get('startup_status', 'NOT_REPORTED')}"
        )
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
        _safe_print_text(
            (
                "Recovered Trades: "
                f"{startup_result.get('recovered_count', 0)}"
            )
        )

        _safe_print_text(
            (
                "Recovered Open Trades: "
                f"{startup_result.get('open_count', 0)}"
            )
        )

        _safe_print_text(
            (
                "Recovered Closed Trades: "
                f"{startup_result.get('closed_count', 0)}"
            )
        )

    startup_error = (
        stats.get(
            "startup_error"
        )
    )

    if startup_error:
        _safe_print_text(
            (
                "Startup Error: "
                f"{startup_error}"
            )
        )

    _safe_print_text(
        (
            "Cycles Started: "
            f"{stats.get('cycles_started', 0)}"
        )
    )

    _safe_print_text(
        (
            "Cycles Completed: "
            f"{stats.get('cycles_completed', 0)}"
        )
    )

    _safe_print_text(
        (
            "Cycles With Errors: "
            f"{stats.get('cycles_with_errors', 0)}"
        )
    )

    _safe_print_text(
        (
            "Opportunity Successes: "
            f"{stats.get('opportunity_successes', 0)}"
        )
    )

    _safe_print_text(
        (
            "Opportunity Failures: "
            f"{stats.get('opportunity_failures', 0)}"
        )
    )

    _safe_print_text(
        (
            "Monitoring Successes: "
            f"{stats.get('monitoring_successes', 0)}"
        )
    )

    _safe_print_text(
        (
            "Monitoring Failures: "
            f"{stats.get('monitoring_failures', 0)}"
        )
    )

    _safe_print_text(
        (
            "Interrupted: "
            f"{stats.get('interrupted', False)}"
        )
    )

    print_runtime_health(
        health_snapshot
    )

    _safe_print_text(
        "\nPAPER TRADING ONLY"
    )

    _safe_print_text(
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
    _configure_utf8_output()

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

        persist_runtime_heartbeat(
            health_snapshot
        )

        print_final_stats(
            stats,
            health_snapshot=(
                health_snapshot
            ),
        )

        return 0

    except KeyboardInterrupt:
        _safe_print_text(
            "\nShutdown requested."
        )

        _safe_print_text(
            "PAPER TRADING ONLY"
        )

        _safe_print_text(
            "NO REAL ORDER WAS PLACED"
        )

        return 0

    except Exception as exc:
        _safe_print_text(
            "\n================================"
        )

        _safe_print_text(
            "RUNTIME ERROR"
        )

        _safe_print_text(
            "================================"
        )

        _safe_print_text(
            (
                "Error: "
                f"{str(exc)}"
            )
        )

        _safe_print_text(
            "\nPAPER TRADING ONLY"
        )

        _safe_print_text(
            "NO REAL ORDER WAS PLACED"
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(
        main()
    )