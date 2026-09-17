import importlib
import subprocess
import sys


P9_EXPORTS = (
    "PaperOrchestrationPolicyV1",
    "PaperOrchestrationFailureV1",
    "PaperOrchestrationStageResultV1",
    "PaperOrchestrationCycleInputV1",
    "PaperOrchestrationCycleResultV1",
)


def test_p9_contracts_are_available_from_package_root():
    contracts = importlib.import_module(
        "services.contracts"
    )

    for name in P9_EXPORTS:
        assert (
            getattr(
                contracts,
                name,
            ).__name__
            == name
        )


def test_p9_package_does_not_import_live_execution_modules():
    # Import-purity must be tested in an isolated interpreter.
    # Removing services.paper_orchestration modules from this pytest
    # process invalidates class identity for already-imported consumers.
    script = """
import importlib
import sys

importlib.import_module(
    "services.paper_orchestration"
)

forbidden = {
    "services.live.live_market_engine",
    "services.execution.order_executor",
    "services.execution.order_manager",
}

loaded = sorted(
    forbidden.intersection(
        sys.modules
    )
)

if loaded:
    print(
        "FORBIDDEN_IMPORTED="
        + ",".join(loaded)
    )
    raise SystemExit(1)

print(
    "P9_IMPORT_PURITY_GREEN=True"
)
"""

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    assert (
        completed.returncode
        == 0
    ), completed.stdout

    assert (
        "P9_IMPORT_PURITY_GREEN=True"
        in completed.stdout
    )
