from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "venv" / "Scripts" / "python.exe"


@pytest.mark.parametrize(
    "token",
    (
        "pandas", "numpy", "scipy", "requests", "yfinance", "smartapi", "streamlit",
        "services.broker", "provider", "services.execution", "news", "sentiment", "nlp", "openai",
    ),
)
def test_scheduled_event_import_isolated(token):
    code = (
        "import importlib,sys;"
        "importlib.import_module('services.contracts.scheduled_market_event_v1');"
        f"print(any({token!r} in name.lower() for name in sys.modules))"
    )
    completed = subprocess.run([str(PYTHON), "-c", code], cwd=ROOT, text=True, capture_output=True, check=True)
    assert completed.stdout.strip() == "False"


def test_contracts_package_keeps_scheduled_event_lazy():
    code = (
        "import services.contracts as contracts,sys;"
        "assert 'services.contracts.scheduled_market_event_v1' not in sys.modules;"
        "assert contracts.ScheduledMarketEventV1.__name__ == 'ScheduledMarketEventV1'"
    )
    subprocess.run([str(PYTHON), "-c", code], cwd=ROOT, text=True, capture_output=True, check=True)
