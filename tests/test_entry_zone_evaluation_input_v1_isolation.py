from __future__ import annotations

import ast
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).parents[1]
CONTRACT_PATH = PROJECT_ROOT / "services" / "contracts" / "entry_zone_evaluation_input_v1.py"


def test_input_contract_imports_only_standard_library_and_identity_normalization() -> None:
    tree = ast.parse(CONTRACT_PATH.read_text(encoding="utf-8"))
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

    assert imported_roots <= {"__future__", "dataclasses", "datetime", "json", "math", "services", "types", "typing"}


def test_input_contract_has_no_wall_clock_calls() -> None:
    source = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "datetime.now" not in source
    assert "utcnow" not in source
    assert "date.today" not in source
    assert "time.time" not in source


def test_fresh_subprocess_import_is_clean() -> None:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    command = (
        "from services.contracts.entry_zone_evaluation_input_v1 import EntryZoneEvaluationInputV1; "
        "from services.contracts import EntryZoneEvaluationInputV1 as PublicInput; "
        "assert EntryZoneEvaluationInputV1 is PublicInput; print('IMPORT_OK')"
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
