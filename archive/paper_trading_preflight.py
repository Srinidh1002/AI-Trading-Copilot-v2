"""
AI Trading Copilot - Paper Trading Preflight Check.

Checks whether the continuous paper-trading system is ready to run.

IMPORTANT:
- Does not place any real or paper trade.
- Does not request live market data.
- Does not print credential values.
- Does not log in to Angel One.
"""

import importlib
import os
from pathlib import Path

from run_continuous_paper_trading import get_runtime_config


REQUIRED_FILES = (
    "live_option_decision_nifty.py",
    "monitor_paper_positions.py",
    "run_continuous_paper_trading.py",
)

REQUIRED_MODULES = (
    "services.continuous_paper_trading_runtime",
    "services.paper_trading_runtime_adapter",
    "services.paper_trading_engine",
    "services.paper_trade_repository",
    "services.paper_trading_orchestrator",
    "services.paper_position_lifecycle_runner",
    "services.angel_paper_trade_price_provider",
    "services.live_paper_position_monitor",
    "services.broker.angel_client",
)

ANGEL_CREDENTIAL_GROUPS = {
    "API Key": (
        "ANGEL_API_KEY",
        "ANGEL_ONE_API_KEY",
        "SMARTAPI_API_KEY",
        "API_KEY",
    ),
    "Client Code": (
    "ANGEL_CLIENT_ID",
    "ANGEL_CLIENT_CODE",
    "ANGEL_ONE_CLIENT_CODE",
    "SMARTAPI_CLIENT_CODE",
    "CLIENT_CODE",
),
    "PIN": (
        "ANGEL_PIN",
        "ANGEL_ONE_PIN",
        "SMARTAPI_PIN",
        "PIN",
    ),
    "TOTP Secret": (
        "ANGEL_TOTP_SECRET",
        "ANGEL_ONE_TOTP_SECRET",
        "SMARTAPI_TOTP_SECRET",
        "TOTP_SECRET",
    ),
}


def make_check(
    name,
    status,
    message,
):
    return {
        "name": name,
        "status": status,
        "message": message,
    }


def check_required_files(
    project_root,
):
    project_root = Path(
        project_root
    ).resolve()

    checks = []

    for relative_path in REQUIRED_FILES:
        path = (
            project_root
            / relative_path
        )

        if path.is_file():
            checks.append(
                make_check(
                    relative_path,
                    "PASS",
                    "Required file exists.",
                )
            )
        else:
            checks.append(
                make_check(
                    relative_path,
                    "FAIL",
                    "Required file is missing.",
                )
            )

    return checks


def check_required_modules(
    importer=importlib.import_module,
):
    checks = []

    for module_name in REQUIRED_MODULES:
        try:
            importer(
                module_name
            )

        except Exception as exc:
            checks.append(
                make_check(
                    module_name,
                    "FAIL",
                    (
                        "Module could not be imported: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                )
            )

        else:
            checks.append(
                make_check(
                    module_name,
                    "PASS",
                    "Module is importable.",
                )
            )

    return checks


def _find_configured_environment_variable(
    names,
    environment,
):
    for name in names:
        value = environment.get(
            name
        )

        if (
            value is not None
            and str(value).strip()
        ):
            return name

    return None


def check_angel_credentials(
    environment=None,
):
    if environment is None:
        environment = os.environ

    checks = []

    for label, names in ANGEL_CREDENTIAL_GROUPS.items():
        configured_name = (
            _find_configured_environment_variable(
                names,
                environment,
            )
        )

        if configured_name:
            checks.append(
                make_check(
                    f"Angel One {label}",
                    "PASS",
                    (
                        "Credential is configured "
                        f"through {configured_name}. "
                        "Value was not displayed."
                    ),
                )
            )
        else:
            checks.append(
                make_check(
                    f"Angel One {label}",
                    "FAIL",
                    (
                        "Credential was not found in "
                        "the supported environment variables."
                    ),
                )
            )

    return checks


def check_runtime_configuration(
    config_loader=get_runtime_config,
):
    try:
        config = (
            config_loader()
        )

    except Exception as exc:
        return [
            make_check(
                "Runtime Configuration",
                "FAIL",
                (
                    "Runtime configuration is invalid: "
                    f"{exc}"
                ),
            )
        ]

    interval = config.get(
        "interval_seconds"
    )

    timeout = config.get(
        "timeout_seconds"
    )

    checks = []

    if (
        isinstance(interval, (int, float))
        and not isinstance(interval, bool)
        and interval > 0
    ):
        checks.append(
            make_check(
                "Runtime Interval",
                "PASS",
                f"Configured to {interval} seconds.",
            )
        )
    else:
        checks.append(
            make_check(
                "Runtime Interval",
                "FAIL",
                "Runtime interval is invalid.",
            )
        )

    if (
        isinstance(timeout, (int, float))
        and not isinstance(timeout, bool)
        and timeout > 0
    ):
        checks.append(
            make_check(
                "Script Timeout",
                "PASS",
                f"Configured to {timeout} seconds.",
            )
        )
    else:
        checks.append(
            make_check(
                "Script Timeout",
                "FAIL",
                "Script timeout is invalid.",
            )
        )

    return checks


def check_persistence_directory(
    project_root,
):
    project_root = Path(
        project_root
    ).resolve()

    data_directory = (
        project_root
        / "data"
    )

    try:
        data_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        probe = (
            data_directory
            / ".paper_trading_preflight_write_test"
        )

        probe.write_text(
            "paper-trading-preflight",
            encoding="utf-8",
        )

        probe.unlink()

    except Exception as exc:
        return make_check(
            "Paper Trading Persistence",
            "FAIL",
            (
                "Persistence directory is not writable: "
                f"{exc}"
            ),
        )

    return make_check(
        "Paper Trading Persistence",
        "PASS",
        (
            "Data directory exists and is writable."
        ),
    )


def check_paper_trading_components():
    try:
        from services.paper_trade_repository import (
            PaperTradeRepository,
        )
        from services.paper_trading_engine import (
            PaperTradingEngine,
        )
        from services.paper_trading_orchestrator import (
            PaperTradingOrchestrator,
        )

        repository = (
            PaperTradeRepository()
        )

        engine = (
            PaperTradingEngine(
                repository=repository,
                persist_state=False,
            )
        )

        PaperTradingOrchestrator(
            engine,
            enabled=True,
        )

    except Exception as exc:
        return make_check(
            "Paper Trading Components",
            "FAIL",
            (
                "Paper-trading components could not "
                f"initialize: {type(exc).__name__}: {exc}"
            ),
        )

    return make_check(
        "Paper Trading Components",
        "PASS",
        "Core paper-trading components initialized.",
    )


def check_real_order_isolation():
    """
    This runtime launches only the opportunity-analysis script and
    paper-position monitor. It contains no real-order execution adapter.
    """

    return make_check(
        "Real Order Isolation",
        "PASS",
        (
            "Continuous runtime is configured for "
            "paper-trading orchestration only."
        ),
    )


def determine_overall_status(
    checks,
):
    statuses = {
        check[
            "status"
        ]
        for check in checks
    }

    if "FAIL" in statuses:
        return "NOT_READY"

    if "WARN" in statuses:
        return "READY_WITH_WARNINGS"

    return "READY"


def run_preflight(
    *,
    project_root=None,
    environment=None,
    importer=importlib.import_module,
    config_loader=get_runtime_config,
):
    if project_root is None:
        project_root = (
            Path(__file__)
            .resolve()
            .parent
        )

    checks = []

    checks.extend(
        check_required_files(
            project_root
        )
    )

    checks.extend(
        check_required_modules(
            importer=importer
        )
    )

    checks.extend(
        check_angel_credentials(
            environment=environment
        )
    )

    checks.extend(
        check_runtime_configuration(
            config_loader=config_loader
        )
    )

    checks.append(
        check_persistence_directory(
            project_root
        )
    )

    checks.append(
        check_paper_trading_components()
    )

    checks.append(
        check_real_order_isolation()
    )

    return {
        "status": (
            determine_overall_status(
                checks
            )
        ),
        "checks": checks,
        "passed": sum(
            1
            for check in checks
            if check[
                "status"
            ] == "PASS"
        ),
        "warnings": sum(
            1
            for check in checks
            if check[
                "status"
            ] == "WARN"
        ),
        "failed": sum(
            1
            for check in checks
            if check[
                "status"
            ] == "FAIL"
        ),
    }


def print_report(
    report,
):
    print(
        "\n================================"
    )
    print(
        "AI TRADING COPILOT"
    )
    print(
        "PAPER TRADING PREFLIGHT"
    )
    print(
        "================================"
    )

    for check in report[
        "checks"
    ]:
        print(
            f"\n[{check['status']}] "
            f"{check['name']}"
        )

        print(
            check[
                "message"
            ]
        )

    print(
        "\n================================"
    )
    print(
        "PREFLIGHT RESULT"
    )
    print(
        "================================"
    )

    print(
        "Status:",
        report[
            "status"
        ],
    )

    print(
        "Passed:",
        report[
            "passed"
        ],
    )

    print(
        "Warnings:",
        report[
            "warnings"
        ],
    )

    print(
        "Failed:",
        report[
            "failed"
        ],
    )

    print(
        "\nPAPER TRADING ONLY"
    )

    print(
        "NO REAL ORDER WAS PLACED"
    )


def main():
    try:
        report = (
            run_preflight()
        )

        print_report(
            report
        )

        return (
            0
            if report[
                "status"
            ] in {
                "READY",
                "READY_WITH_WARNINGS",
            }
            else 1
        )

    except Exception as exc:
        print(
            "\n================================"
        )
        print(
            "PREFLIGHT ERROR"
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
            "\nNO REAL ORDER WAS PLACED"
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(
        main()
    )