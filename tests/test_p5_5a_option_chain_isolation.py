"""Clean-process import isolation for the provider-neutral P5-5A runtime."""
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "venv" / "Scripts" / "python.exe"
MODULES = (
    "services.option_chain_intelligence",
    "services.option_chain_intelligence.normalization",
    "services.option_chain_intelligence.quality",
    "services.option_chain_intelligence.pipeline",
)
# Each token represents an independently prohibited integration boundary.  The
# test deliberately runs in fresh interpreters because pytest itself may load
# unrelated modules while collecting the repository's broader test suite.
FORBIDDEN_MODULE_TOKENS = (
    "pandas",
    "numpy",
    "yfinance",
    "requests",
    "urllib",
    "smartapi",
    "angel",
    "nse",
    "streamlit",
    "provider",
    "broker",
    # ``linecache`` is a Python import implementation detail, not an
    # application cache; guard concrete cache integration packages instead.
    "diskcache",
    "redis",
    "sqlite",
    "sqlalchemy",
    "technical_intelligence",
    "regime",
    "ranking",
    "services.risk",
    "services.paper",
    "dashboard",
    "config",
)


@pytest.mark.parametrize("module", MODULES)
@pytest.mark.parametrize("token", FORBIDDEN_MODULE_TOKENS)
def test_clean_import_loads_no_prohibited_dependency(module, token):
    code = (
        "import importlib, sys; "
        f"importlib.import_module({module!r}); "
        f"print(any({token!r} in name.lower() for name in sys.modules))"
    )
    result = subprocess.run(
        [str(PYTHON), "-c", code],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout.strip() == "False"
