"""Compatibility wrapper for the archived pre-market readiness CLI."""

from pathlib import Path as _Path

_ARCHIVED_FILE = _Path(__file__).with_name("archive") / "pre_market_readiness.py"
exec(compile(_ARCHIVED_FILE.read_text(encoding="utf-8"), str(_ARCHIVED_FILE), "exec"), globals())
