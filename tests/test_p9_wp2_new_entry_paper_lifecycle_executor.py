import subprocess
import sys

from services.paper_orchestration.new_entry_paper_lifecycle_executor import (
    NewEntryPaperLifecycleExecutor,
)


def test_module_does_not_import_live_or_legacy_execution():
    script = """
import json
import sys

before = set(sys.modules)

import services.paper_orchestration.new_entry_paper_lifecycle_executor

after = set(sys.modules)
newly_imported = after - before

forbidden = {
    "services.live.live_market_engine",
    "services.execution.order_executor",
    "services.execution.order_manager",
    "services.paper_trading_engine",
    "services.paper_trading.paper_trading_engine_adapter_v1",
}

print(json.dumps(sorted(forbidden.intersection(newly_imported))))
"""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == "[]"


def test_executor_exposes_only_typed_persistence_dependencies():
    annotations = NewEntryPaperLifecycleExecutor.__init__.__annotations__

    assert "portfolio_persistence_service" in annotations
    assert "trade_persistence_service" in annotations