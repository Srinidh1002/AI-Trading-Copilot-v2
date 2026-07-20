"""Compatibility wrapper for the archived audit-log CLI."""

from pathlib import Path as _Path

_ARCHIVED_FILE = _Path(__file__).with_name("archive") / "inspect_audit_log.py"
exec(compile(_ARCHIVED_FILE.read_text(encoding="utf-8"), str(_ARCHIVED_FILE), "exec"), globals())
