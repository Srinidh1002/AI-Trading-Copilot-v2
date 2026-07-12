"""
Continuous Paper Trading Entry Point.

Coordinates:

ContinuousPaperTradingRuntime
    -> PaperTradingRuntimeAdapter
        -> live_option_decision_nifty.py
        -> monitor_paper_positions.py

IMPORTANT:
- PAPER TRADING ONLY.
- NO REAL ORDER PLACEMENT.
- Existing standalone scripts run in isolated subprocesses.
"""

import os
from pathlib import Path

from services.continuous_paper_trading_runtime import (
    ContinuousPaperTradingRuntime,
)
from services.paper_trading_runtime_adapter import (
    PaperTradingRuntimeAdapter,
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

    Non-zero exits, timeouts, and execution failures become exceptions so
    ContinuousPaperTradingRuntime records them as operation failures.
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


def build_runtime(
    *,
    config=None,
    adapter_factory=PaperTradingRuntimeAdapter,
    runtime_factory=ContinuousPaperTradingRuntime,
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

    runtime = (
        runtime_factory(
            opportunity_cycle=(
                opportunity_cycle
            ),
            monitoring_cycle=(
                monitoring_cycle
            ),
            interval_seconds=(
                config[
                    "interval_seconds"
                ]
            ),
        )
    )

    return (
        runtime,
        adapter,
    )


def print_final_stats(
    stats,
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

        print_final_stats(
            stats
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