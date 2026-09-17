from __future__ import annotations

import inspect
import subprocess
import sys

from services.contracts import PaperTradePositionV1
import services.contracts.paper_trade_position_v1 as position_module


def test_public_export_resolves_exact_contract():
    assert PaperTradePositionV1 is position_module.PaperTradePositionV1


def test_position_contract_source_has_no_prohibited_runtime_dependencies():
    source = inspect.getsource(position_module).lower()
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
        "provider",
    )
    for token in prohibited:
        assert token not in source


def test_fresh_subprocess_public_import_is_clean():
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from services.contracts import PaperTradePositionV1;"
                "assert PaperTradePositionV1.__name__ == 'PaperTradePositionV1'"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
