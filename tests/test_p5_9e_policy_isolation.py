from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "venv" / "Scripts" / "python.exe"


@pytest.mark.parametrize(
    "token",
    ("pandas", "numpy", "scipy", "requests", "yfinance", "smartapi", "streamlit", "provider", "broker", "execution", "news", "nlp", "openai", "random"),
)
def test_external_context_policy_import_isolated(token):
    code = (
        "import importlib,sys;"
        "importlib.import_module('services.contracts.external_context_policy_v1');"
        f"print(any({token!r} in name.lower() for name in sys.modules))"
    )
    completed = subprocess.run([str(PYTHON), "-c", code], cwd=ROOT, text=True, capture_output=True, check=True)
    assert completed.stdout.strip() == "False"
