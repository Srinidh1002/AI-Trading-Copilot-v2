"""Part 16 — dependency lock smoke check. Imports only; no network."""
from __future__ import annotations

import importlib
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]

REQUIRED = (
    "dotenv",
    "pandas",
    "numpy",
    "requests",
    "yfinance",
    "websocket",
    "websockets",
    "fyers_apiv3",
    "SmartApi",
    "pyotp",
    "logzero",
)


def test_runtime_lock_file_exists_and_parses():
    lock = REPO / "requirements-runtime-lock.txt"
    assert lock.is_file(), "requirements-runtime-lock.txt must exist"
    text = lock.read_text(encoding="utf-8")
    assert "Python: 3.12.10" in text
    pins = 0
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        assert "==" in line, f"unpinned entry: {line!r}"
        assert ">" not in line and "<" not in line, f"range entry: {line!r}"
        pins += 1
    assert pins >= 8, f"expected >= 8 pinned deps, got {pins}"


def test_every_required_import_resolves():
    failed = []
    for mod in REQUIRED:
        try:
            importlib.import_module(mod)
        except Exception as exc:
            failed.append((mod, type(exc).__name__, str(exc)[:80]))
    assert not failed, f"failed imports: {failed}"


def test_python_version_recorded():
    text = (REPO / "requirements-runtime-lock.txt").read_text(encoding="utf-8")
    assert "Python: 3.12.10" in text
