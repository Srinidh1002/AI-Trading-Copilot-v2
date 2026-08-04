import importlib
import sys


P9_EXPORTS = (
    "PaperOrchestrationPolicyV1",
    "PaperOrchestrationFailureV1",
    "PaperOrchestrationStageResultV1",
    "PaperOrchestrationCycleInputV1",
    "PaperOrchestrationCycleResultV1",
)


def test_p9_contracts_are_available_from_package_root():
    contracts = importlib.import_module("services.contracts")
    for name in P9_EXPORTS:
        assert getattr(contracts, name).__name__ == name


def test_p9_package_does_not_import_live_execution_modules():
    for name in tuple(sys.modules):
        if name.startswith("services.paper_orchestration"):
            sys.modules.pop(name, None)

    importlib.import_module("services.paper_orchestration")

    forbidden = {
        "services.live.live_market_engine",
        "services.execution.order_executor",
        "services.execution.order_manager",
    }
    assert forbidden.isdisjoint(sys.modules)
