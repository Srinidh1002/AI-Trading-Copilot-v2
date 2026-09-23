"""PID-based supervisor lock. Windows- and POSIX-safe.

Refuses to start if another live supervisor holds the lock.
Cleans up stale locks from dead PIDs automatically.
"""
from __future__ import annotations

import atexit
import os
import sys

_LOCK_DIR = os.path.join("logs", "supervisor")
LOCK_PATH = os.path.join(_LOCK_DIR, ".lock")


def _pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            return bool(ok) and code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_lock():
    try:
        with open(LOCK_PATH, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def acquire() -> None:
    os.makedirs(_LOCK_DIR, exist_ok=True)
    existing = _read_lock()
    if existing is not None and existing != os.getpid() and _pid_alive(existing):
        raise RuntimeError(
            f"supervisor already running (pid={existing}). "
            f"If you are certain it is dead, delete {LOCK_PATH}."
        )
    with open(LOCK_PATH, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    atexit.register(release)


def release() -> None:
    try:
        if os.path.exists(LOCK_PATH):
            with open(LOCK_PATH, "r", encoding="utf-8") as f:
                contents = f.read().strip()
            if contents == str(os.getpid()):
                os.unlink(LOCK_PATH)
    except OSError:
        pass
