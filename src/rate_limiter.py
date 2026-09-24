"""Cross-process FYERS rate limiter for the five-market PAPER runtime.

Replaces the Angel-era per-process limiter. All workers share one
budget via a file-backed token bucket so the aggregate stays under the
provider limit regardless of how many workers run.

FYERS Standard documented limits (2026-09):
  * 10 req/sec
  * 200 req/min
  * 100,000 req/day

We use conservative headroom: 8/sec, 170/min. The extra 30/min of
provider capacity absorbs retries and any clock skew between workers.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from services.paper_orchestration.process_lock_v2 import (
    FileRegionLockError,
    acquire_file_region_lock,
    release_file_region_lock,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_STATE_PATH = _REPO_ROOT / "data" / "rate_limit" / "state.json"
_DAY_BUCKET_SECONDS = 86400
_MINUTE_BUCKET_SECONDS = 60
_SECOND_BUCKET_SECONDS = 1

# FYERS Standard with headroom
_LIMITS = {
    "per_second": 8,
    "per_minute": 170,
    "per_day": 90_000,
}


class FyersRateLimitError(RuntimeError):
    """Limiter authority is unavailable; the provider request must not run."""


def _prune(calls, now):
    cutoff = now - _DAY_BUCKET_SECONDS
    return [t for t in calls if t > cutoff]


def _counts(calls, now):
    return {
        "sec": sum(1 for t in calls if t > now - _SECOND_BUCKET_SECONDS),
        "min": sum(1 for t in calls if t > now - _MINUTE_BUCKET_SECONDS),
        "day": len(calls),
    }


@contextmanager
def _exclusive_file_lock(path: Path):
    """Acquire a real OS lock that is released if this process exits."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(path, "a+b")  # noqa: SIM115
    except OSError as exc:
        raise FyersRateLimitError("RATE_LIMIT_LOCK_UNAVAILABLE") from exc
    try:
        acquire_file_region_lock(handle, blocking=True)
        yield
    except FyersRateLimitError:
        raise
    except (FileRegionLockError, OSError) as exc:
        raise FyersRateLimitError("RATE_LIMIT_LOCK_UNAVAILABLE") from exc
    finally:
        try:
            release_file_region_lock(handle)
        except FileRegionLockError:
            pass
        handle.close()


class FyersRateLimitCoordinator:
    """Single global budget shared across all worker processes."""

    def __init__(self, *, state_path=None, worker_name: str | None = None):
        self._state_path = Path(state_path).resolve() if state_path else _STATE_PATH
        self._lock_path = self._state_path.with_suffix(self._state_path.suffix + ".lock")
        self._worker = worker_name or os.getenv("WORKER_NAME", "unknown")

    def _read(self):
        if not self._state_path.exists():
            return {"calls": []}
        try:
            raw = json.loads(self._state_path.read_text(encoding="utf-8"))
            calls = raw.get("calls") if isinstance(raw, dict) else None
            if not isinstance(calls, list):
                raise ValueError("calls must be a list")  # noqa: TRY004
            return {"calls": [float(timestamp) for timestamp in calls]}
        except (OSError, ValueError, TypeError) as exc:
            raise FyersRateLimitError("RATE_LIMIT_STATE_INVALID") from exc

    def _write(self, state):
        d = self._state_path.parent
        fd, tmp = tempfile.mkstemp(prefix=".rate_limit_", suffix=".json", dir=str(d))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, separators=(",", ":"))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self._state_path)
        except OSError as exc:
            try:
                os.unlink(tmp)
            except Exception:  # noqa: S110, BLE001
                pass
            raise FyersRateLimitError("RATE_LIMIT_STATE_WRITE_FAILED") from exc

    def wait_if_needed(self, endpoint: str = "default"):
        """Block until a call can proceed within the shared budget.

        endpoint parameter is kept for signature compatibility with the
        legacy AngelRateLimitCoordinator. All calls share the same bucket
        because FYERS applies one quota per account, not per endpoint.
        """
        while True:
            with _exclusive_file_lock(self._lock_path):
                now = time.time()
                state = self._read()
                calls = _prune(state["calls"], now)
                c = _counts(calls, now)

                if c["sec"] >= _LIMITS["per_second"]:
                    # Wait until the oldest of the last-second calls ages out
                    recent = sorted(t for t in calls if t > now - _SECOND_BUCKET_SECONDS)
                    sleep_for = 1.05 - (now - recent[0]) if recent else 0.2
                elif c["min"] >= _LIMITS["per_minute"]:
                    recent = sorted(t for t in calls if t > now - _MINUTE_BUCKET_SECONDS)
                    # Sleep until the oldest minute-window call ages out, capped at 5s
                    sleep_for = min(5.0, 60.0 - (now - recent[0])) if recent else 1.0
                elif c["day"] >= _LIMITS["per_day"]:
                    # Day cap; unrecoverable in-session, back off hard.
                    sleep_for = 30.0
                else:
                    calls.append(now)
                    self._write({"calls": calls})
                    return True

            time.sleep(max(0.1, sleep_for))

    def stats(self):
        now = time.time()
        with _exclusive_file_lock(self._lock_path):
            calls = _prune(self._read()["calls"], now)
            return _counts(calls, now)


# Backward-compatible alias so existing imports keep working.
AngelRateLimitCoordinator = FyersRateLimitCoordinator


if __name__ == "__main__":
    rl = FyersRateLimitCoordinator()
    start = time.time()
    for i in range(20):
        rl.wait_if_needed()
        if i % 5 == 4:
            print(f"  {i + 1} calls in {time.time() - start:.2f}s")
    print("stats:", rl.stats())
