from __future__ import annotations

import inspect
import subprocess
import sys

from services.contracts import PaperTradeEntryEvaluationInputV1
import services.contracts.paper_trade_entry_evaluation_input_v1 as input_module


def test_public_export_resolves_exact_contract():
    assert (
        PaperTradeEntryEvaluationInputV1
        is input_module.PaperTradeEntryEvaluationInputV1
    )


def test_entry_input_source_has_no_prohibited_runtime_dependencies():
    source = inspect.getsource(input_module).lower()
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
                "from services.contracts import "
                "PaperTradeEntryEvaluationInputV1;"
                "assert PaperTradeEntryEvaluationInputV1.__name__ == "
                "'PaperTradeEntryEvaluationInputV1'"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
