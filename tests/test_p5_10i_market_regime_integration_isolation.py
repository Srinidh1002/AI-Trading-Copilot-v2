"""Fresh-process import isolation for the P5-10I facade."""
import subprocess
import sys
from pathlib import Path


def test_service_and_package_import_stay_lightweight():
    root = Path(__file__).resolve().parents[1]
    command = (
        "import sys; import services.market_regime; "
        "from services.market_regime.service import evaluate_market_regime; "
        "blocked=('pandas','numpy','scipy','requests','yfinance','SmartApi','smartapi','streamlit'); "
        "print(any(name in sys.modules for name in blocked))"
    )
    completed = subprocess.run([sys.executable, "-c", command], cwd=root, check=True, text=True, capture_output=True)
    assert completed.stdout.strip() == "False"
