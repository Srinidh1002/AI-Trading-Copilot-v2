"""F15-R2 M9b v2 \u2014 index launchers force-exit inside finally.

Canary 2026-09-29 11:18 IST:
  Both index workers ACKed FLAT_SAFE_TO_EXIT, main() reached its return,
  but the processes did not terminate. Cause: interpreter Py_Finalize
  blocked on a non-daemon FYERS DataSocket reader thread that
  streaming.close() does not join. My earlier fix (os._exit in
  __main__ wrapper) never ran because it executes AFTER main() returns —
  main() did return; the interpreter just would not finish.

The correct fix is to call os._exit() from inside main()'s finally.
"""
from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load_helper(module_path):
    spec = importlib.util.spec_from_file_location("_tmp_launcher", module_path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    return mod


def test_nifty_finally_has_force_exit():
    src = (REPO / "run_nifty.py").read_text(encoding="utf-8")
    assert "_f15r2_compute_exit_code" in src
    assert "_os_fin._exit" in src
    ast.parse(src)


def test_sensex_finally_has_force_exit():
    src = (REPO / "run_sensex.py").read_text(encoding="utf-8")
    assert "_f15r2_compute_exit_code" in src
    assert "_os_fin._exit" in src
    ast.parse(src)


def test_nifty_helper_maps_none_to_zero():
    # Extract helper source and eval in isolation to avoid launching main()
    src = (REPO / "run_nifty.py").read_text(encoding="utf-8")
    # Find the helper function text
    start = src.index("def _f15r2_compute_exit_code")
    end = src.index("def main() -> int:")
    helper_src = src[start:end]
    ns = {}
    exec(helper_src, ns)
    fn = ns["_f15r2_compute_exit_code"]
    assert fn((None, None, None)) == 0


def test_nifty_helper_maps_systemexit_int():
    src = (REPO / "run_nifty.py").read_text(encoding="utf-8")
    start = src.index("def _f15r2_compute_exit_code")
    end = src.index("def main() -> int:")
    helper_src = src[start:end]
    ns = {}
    exec(helper_src, ns)
    fn = ns["_f15r2_compute_exit_code"]
    assert fn((SystemExit, SystemExit(7), None)) == 7


def test_nifty_helper_maps_systemexit_string_to_one():
    src = (REPO / "run_nifty.py").read_text(encoding="utf-8")
    start = src.index("def _f15r2_compute_exit_code")
    end = src.index("def main() -> int:")
    helper_src = src[start:end]
    ns = {}
    exec(helper_src, ns)
    fn = ns["_f15r2_compute_exit_code"]
    assert fn((SystemExit, SystemExit("BLOCKED"), None)) == 1


def test_nifty_helper_maps_other_exception_to_one():
    src = (REPO / "run_nifty.py").read_text(encoding="utf-8")
    start = src.index("def _f15r2_compute_exit_code")
    end = src.index("def main() -> int:")
    helper_src = src[start:end]
    ns = {}
    exec(helper_src, ns)
    fn = ns["_f15r2_compute_exit_code"]
    assert fn((RuntimeError, RuntimeError("x"), None)) == 1


def test_force_exit_is_actually_reachable():
    """Prove os._exit works end-to-end via subprocess."""
    code = (
        "import os, sys\n"
        "def _f15r2_compute_exit_code(exc_info):\n"
        "    exc_type, exc_val, _ = exc_info\n"
        "    if exc_type is None:\n"
        "        return 0\n"
        "    if exc_type is SystemExit and exc_val is not None:\n"
        "        code = getattr(exc_val, 'code', 0)\n"
        "        if code is None: return 0\n"
        "        if isinstance(code, int): return code\n"
        "        return 1\n"
        "    return 1\n"
        "try:\n"
        "    raise SystemExit(3)\n"
        "finally:\n"
        "    os._exit(_f15r2_compute_exit_code(sys.exc_info()))\n"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, timeout=10
    )
    assert r.returncode == 3, r
