"""Exclusive supervisor ownership lock; stale metadata cannot retain an OS lock."""

from __future__ import annotations

from pathlib import Path

from services.paper_orchestration.process_lock_v2 import ProcessLockV2

_REPO_ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = _REPO_ROOT / "logs" / "supervisor" / ".lock"
_lock: ProcessLockV2 | None = None


def acquire() -> ProcessLockV2:
    global _lock
    if _lock is None:
        _lock = ProcessLockV2(LOCK_PATH, role="SUPERVISOR").acquire()
    return _lock


def release() -> None:
    global _lock
    if _lock is not None:
        _lock.release()
        _lock = None
