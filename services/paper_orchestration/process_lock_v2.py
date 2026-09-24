"""Cross-platform, crash-safe process ownership locks for the PAPER runtime.

Windows-safe design:

  <path>            metadata file — human-readable, never byte-locked
  <path>.guard      byte-range authority — never holds application data

The Windows byte-range lock (msvcrt.locking) is held on <path>.guard for the
full ownership lifetime.  Because the metadata file is not the file being
locked, any other process can inspect ownership without disturbing the holder,
and the earlier failure mode of "locked file is unreadable" cannot occur.

Crash safety: when the owning process exits (normally or not), the OS releases
the guard byte-range.  Any stale metadata on disk is harmless; the next
acquirer replaces it atomically.
"""

from __future__ import annotations

import atexit
import errno
import json
import os
import secrets
import tempfile
from datetime import UTC, datetime
from pathlib import Path


class ProcessLockError(RuntimeError):
    """Public lock failure.

    Reason prefix distinguishes contention (LOCK_HELD) from internal faults
    (LOCK_INTERNAL_ERROR) and metadata-write failures
    (LOCK_METADATA_WRITE_FAILED).
    """


class FileRegionLockError(RuntimeError):
    """The operating system could not establish a byte-range lock."""


class FileRegionAlreadyLocked(FileRegionLockError):
    """Another live process owns the requested byte range."""


_LOCK_OFFSET = 0
_LOCK_LENGTH = 1
_GUARD_SUFFIX = ".guard"


def _is_contention_error(exc: OSError) -> bool:
    return exc.errno in {errno.EACCES, errno.EAGAIN, errno.EPERM, errno.EDEADLK}


def _open_guard(guard_path: Path):
    """Open the guard file read/write, creating it if absent.

    r+b (not a+b) is required on Windows: append mode ignores seek on write,
    which is incompatible with byte-range locking semantics.
    """
    guard_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(guard_path), os.O_RDWR | os.O_CREAT, 0o600)
    return os.fdopen(fd, "r+b")


def acquire_file_region_lock(handle, *, blocking: bool) -> None:
    """Acquire an exclusive byte-range lock at byte 0 and retain the handle.

    The caller keeps ``handle`` open for the entire ownership lifetime; the
    OS releases the lock when the handle is closed or the process exits.
    """
    try:
        handle.seek(_LOCK_OFFSET)
        if os.name == "nt":
            import msvcrt

            mode = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
            msvcrt.locking(handle.fileno(), mode, _LOCK_LENGTH)
        else:
            import fcntl

            mode = fcntl.LOCK_EX
            if not blocking:
                mode |= fcntl.LOCK_NB
            fcntl.flock(handle.fileno(), mode)
    except OSError as exc:
        if _is_contention_error(exc):
            raise FileRegionAlreadyLocked("LOCK_HELD") from exc
        raise FileRegionLockError("LOCK_ACQUIRE_FAILED") from exc


def release_file_region_lock(handle) -> None:
    """Release exactly the byte range acquired by acquire_file_region_lock."""
    try:
        handle.seek(_LOCK_OFFSET)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, _LOCK_LENGTH)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError as exc:
        raise FileRegionLockError("LOCK_RELEASE_FAILED") from exc


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(json.dumps(payload, sort_keys=True).encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class ProcessLockV2:
    """Exclusive OS lock with diagnostic owner metadata.

    Metadata lives at ``path`` and is written atomically.  The byte-range
    authority lives at ``path + '.guard'`` and is never inspected for content.
    """

    def __init__(self, path, *, role: str):
        self.path = Path(path).resolve()
        self.guard_path = self.path.with_name(self.path.name + _GUARD_SUFFIX)
        self.role = str(role)
        self._handle = None
        self.owner = {
            "pid": os.getpid(),
            "role": self.role,
            "started_at_utc": datetime.now(UTC).isoformat(),
            "nonce": secrets.token_hex(16),
        }

    @property
    def held(self) -> bool:
        return self._handle is not None

    def acquire(self) -> ProcessLockV2:
        if self._handle is not None:
            return self
        handle = None
        try:
            handle = _open_guard(self.guard_path)
            acquire_file_region_lock(handle, blocking=False)
        except FileRegionAlreadyLocked as exc:
            if handle is not None:
                try:
                    handle.close()
                except OSError:
                    pass
            raise ProcessLockError(f"LOCK_HELD:{self.role}") from exc
        except FileRegionLockError as exc:
            if handle is not None:
                try:
                    handle.close()
                except OSError:
                    pass
            raise ProcessLockError(f"LOCK_INTERNAL_ERROR:{self.role}") from exc
        except OSError as exc:
            if handle is not None:
                try:
                    handle.close()
                except OSError:
                    pass
            raise ProcessLockError(f"LOCK_INTERNAL_ERROR:{self.role}") from exc

        try:
            _atomic_write_json(self.path, self.owner)
        except OSError as exc:
            try:
                release_file_region_lock(handle)
            except FileRegionLockError:
                pass
            try:
                handle.close()
            except OSError:
                pass
            raise ProcessLockError(f"LOCK_METADATA_WRITE_FAILED:{self.role}") from exc

        self._handle = handle
        atexit.register(self.release)
        return self

    def release(self) -> None:
        if self._handle is None:
            return
        handle, self._handle = self._handle, None
        try:
            release_file_region_lock(handle)
        except FileRegionLockError:
            pass
        try:
            handle.close()
        except OSError:
            pass


def lock_available(path, *, role: str) -> bool:
    """Return True if the logical lock can be acquired right now.

    Does not write or replace metadata.  Does not leave any lock behind.
    Never raises for ordinary contention.
    """
    logical = Path(path).resolve()
    guard_path = logical.with_name(logical.name + _GUARD_SUFFIX)
    try:
        handle = _open_guard(guard_path)
    except OSError:
        return False
    try:
        try:
            acquire_file_region_lock(handle, blocking=False)
        except FileRegionAlreadyLocked:
            return False
        except FileRegionLockError:
            return False
        try:
            release_file_region_lock(handle)
        except FileRegionLockError:
            pass
        return True
    finally:
        try:
            handle.close()
        except OSError:
            pass
