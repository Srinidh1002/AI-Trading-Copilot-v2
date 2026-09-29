"""F15-R2 M9b \u2014 index worker hard-exit after main().

Canary 2026-09-29: after FLAT_ACK_EXIT, run_nifty.py's parent process
stayed alive indefinitely because the FYERS DataSocket reader thread is
non-daemon and never joined within interpreter shutdown. Supervisor's
grace window elapsed without the worker's process actually terminating.

Fix: wrap main() in a try that captures SystemExit code, flush stdio,
then os._exit() to bypass lingering non-daemon threads.
"""
from __future__ import annotations

import ast
from pathlib import Path


def test_run_nifty_hard_exits_after_main():
    src = Path("run_nifty.py").read_text(encoding="utf-8")
    assert "._exit(_code)" in src
    assert "_os_exit._exit(_code)" in src
    assert "raise SystemExit(main())" not in src


def test_run_sensex_hard_exits_after_main():
    src = Path("run_sensex.py").read_text(encoding="utf-8")
    assert "._exit(_code)" in src
    assert "_os_exit._exit(_code)" in src
    assert "raise SystemExit(main())" not in src


def test_run_nifty_preserves_systemexit_code():
    src = Path("run_nifty.py").read_text(encoding="utf-8")
    assert "except SystemExit as _se" in src
    assert "_se.code if isinstance(_se.code, int) else 0" in src


def test_run_sensex_preserves_systemexit_code():
    src = Path("run_sensex.py").read_text(encoding="utf-8")
    assert "except SystemExit as _se" in src
    assert "_se.code if isinstance(_se.code, int) else 0" in src


def test_run_nifty_imports_are_clean():
    src = Path("run_nifty.py").read_text(encoding="utf-8")
    ast.parse(src)


def test_run_sensex_imports_are_clean():
    src = Path("run_sensex.py").read_text(encoding="utf-8")
    ast.parse(src)
