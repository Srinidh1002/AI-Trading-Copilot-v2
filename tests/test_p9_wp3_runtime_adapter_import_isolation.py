import subprocess
import sys


def test_runtime_adapter_does_not_load_live_or_legacy_execution():
    code = """
import sys
before = set(sys.modules)
import services.paper_orchestration.continuous_runtime_adapter
import services.paper_orchestration.restart_recovery_operation
after = set(sys.modules)
forbidden = {
    'services.paper_trading_engine',
    'services.paper_trading.paper_trading_engine_adapter_v1',
    'services.live_market_engine',
    'services.execution.order_executor',
    'services.execution.order_manager',
}
print(sorted(forbidden.intersection(after - before)))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == "[]"
