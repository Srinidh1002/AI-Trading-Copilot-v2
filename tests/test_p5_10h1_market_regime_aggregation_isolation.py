"""Import isolation coverage for the P5-10H1 aggregate module."""
import subprocess
import sys
from pathlib import Path


def test_aggregate_import_does_not_load_optional_runtime_modules():
    root = Path(__file__).resolve().parents[1]
    command = (
        "import sys; from services.market_regime.aggregate import aggregate_market_regime; "
        "blocked=('pandas','numpy','scipy','requests','yfinance','SmartApi','smartapi','streamlit'); "
        "print(any(name in sys.modules for name in blocked))"
    )
    completed = subprocess.run([sys.executable, "-c", command], cwd=root, check=True, text=True, capture_output=True)
    assert completed.stdout.strip() == "False"
