from __future__ import annotations

import inspect
import subprocess
import sys

from services.contracts import PaperTradeFillV1
import services.contracts.paper_trade_fill_v1 as fill_module


def test_public_export_resolves_exact_contract():
    assert PaperTradeFillV1 is fill_module.PaperTradeFillV1


def test_fill_contract_source_has_no_prohibited_runtime_dependencies():
    source = inspect.getsource(fill_module).lower()
    prohibited = (
        "papertradingengine",
        "yfinance",
        "streamlit",
        "pandas",
        "numpy",
        "scipy",
        "datetime.now",
        "date.today",
        "uuid.uuid",
        "requests.",
        "broker",
        "order placement",
        "database",
        "pnl",
    )
    for token in prohibited:
        assert token not in source


def test_fresh_subprocess_public_import_is_clean():
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from services.contracts import PaperTradeFillV1;"
                "assert PaperTradeFillV1.__name__ == 'PaperTradeFillV1'"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
