"""Fresh-process isolation replay for P5-10J."""
import subprocess
import sys
from pathlib import Path


def test_replay_import_remains_provider_and_runtime_free():
    root = Path(__file__).resolve().parents[1]
    command = (
        "import sys; from services.market_regime import evaluate_market_regime; "
        "blocked=('pandas','numpy','scipy','requests','yfinance','SmartApi','smartapi','streamlit'); "
        "print(any(name in sys.modules for name in blocked))"
    )
    completed = subprocess.run([sys.executable, "-c", command], cwd=root, check=True, text=True, capture_output=True)
    assert completed.stdout.strip() == "False"
