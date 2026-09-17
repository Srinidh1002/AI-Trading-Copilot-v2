from __future__ import annotations

import ast
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).parents[1]
EVALUATOR_PATH = PROJECT_ROOT / "services" / "trade_planning" / "entry_zone_evaluator.py"


def test_evaluator_imports_only_contract_types_and_typing() -> None:
    tree = ast.parse(EVALUATOR_PATH.read_text(encoding="utf-8"))
    imported_roots = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }

    assert imported_roots <= {"__future__", "services", "typing"}


def test_evaluator_has_no_wall_clock_or_order_calls() -> None:
    source = EVALUATOR_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "datetime.now",
        "utcnow",
        "date.today",
        "time.time",
        "place_order",
        "submit_order",
        "execute_order",
        "cancel_order",
    ):
        assert forbidden not in source


def test_fresh_subprocess_import_is_clean() -> None:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    command = (
        "from services.trade_planning.entry_zone_evaluator import evaluate_entry_zone; "
        "from services.trade_planning import evaluate_entry_zone as PublicEvaluator; "
        "assert evaluate_entry_zone is PublicEvaluator; print('IMPORT_OK')"
    )

    completed = subprocess.run(
        [sys.executable, "-c", command],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "IMPORT_OK"
