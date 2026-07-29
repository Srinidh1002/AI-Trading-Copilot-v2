from __future__ import annotations

import ast
from pathlib import Path


PURE_FILES = (
    "services/paper_portfolio/paper_portfolio_lock_evaluator.py",
    "services/paper_portfolio/paper_capital_reservation_manager.py",
    "services/paper_portfolio/paper_portfolio_aggregation.py",
    "services/paper_portfolio/paper_portfolio_admission_evaluator.py",
    "services/paper_portfolio/paper_portfolio_reconciliation.py",
)

PROHIBITED_PREFIXES = (
    "requests",
    "yfinance",
    "streamlit",
    "services.brokers",
    "services.providers",
    "services.paper_trading_engine",
)


def test_p8_pure_modules_do_not_import_prohibited_dependencies():
    for filename in PURE_FILES:
        tree = ast.parse(Path(filename).read_text(encoding="utf-8"), filename=filename)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        assert not any(
            name.startswith(prefix)
            for name in imported
            for prefix in PROHIBITED_PREFIXES
        ), (filename, imported)


def test_p8_pure_modules_do_not_generate_runtime_identity_or_time():
    banned = ("uuid4(", "datetime.now(", "date.today(", "random.")
    for filename in PURE_FILES:
        text = Path(filename).read_text(encoding="utf-8")
        assert not any(token in text for token in banned), filename
