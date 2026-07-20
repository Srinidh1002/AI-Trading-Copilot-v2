"""Compatibility wrapper for the archived paper-trading preflight CLI."""

from pathlib import Path as _Path

_ARCHIVED_FILE = _Path(__file__).with_name("archive") / "paper_trading_preflight.py"
exec(compile(_ARCHIVED_FILE.read_text(encoding="utf-8"), str(_ARCHIVED_FILE), "exec"), globals())
