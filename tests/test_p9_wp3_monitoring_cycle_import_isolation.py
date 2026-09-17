import subprocess
import sys


def test_monitoring_cycle_executor_does_not_load_live_or_legacy_execution():
    code = """
import sys
before = set(sys.modules)
import services.paper_orchestration.existing_position_monitoring_cycle_executor
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
