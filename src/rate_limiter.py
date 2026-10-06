"""Cross-process FYERS request budget for the five-market PAPER runtime.

Every synchronous FYERS REST request must consume this shared file-backed
budget before reaching the SDK.  The limiter intentionally uses a conservative
local safety envelope instead of assuming that every FYERS endpoint has the
same provider-side quota.

A provider 429 is also recorded in this shared state.  That creates a short
cross-process cooldown so the other workers do not continue a request storm.
The failed request is not retried here; callers keep their existing fail-closed
semantics.
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
_LIVE_STATE_PATH = _REPO_ROOT / "data" / "rate_limit" / "state.json"


def _default_state_path():
    """Return the default limiter state path.

    Offline tests set FYERS_RATE_LIMIT_STATE_PATH to a temporary file so no
    test can mutate the live runtime budget.
    """
    override = os.environ.get("FYERS_RATE_LIMIT_STATE_PATH")
    if override:
        return Path(override)
    return _LIVE_STATE_PATH


_DAY_BUCKET_SECONDS = 86400
_MINUTE_BUCKET_SECONDS = 60
_SECOND_BUCKET_SECONDS = 1

# R18: intentionally conservative aggregate safety envelope.  This is a local
# runtime guard, not a claim about the provider's contractual quota.
_LIMITS = {
    "per_second": 4,
    "per_minute": 120,
    "per_day": 90_000,
}

_RATE_LIMIT_BASE_COOLDOWN_SECONDS = 5.0
_RATE_LIMIT_MAX_COOLDOWN_SECONDS = 60.0
_RATE_LIMIT_STREAK_WINDOW_SECONDS = 60.0


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


def _default_state():
    return {
        "calls": [],
        "cooldown_until": 0.0,
        "rate_limit_streak": 0,
        "last_rate_limit_at": 0.0,
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
        self._state_path = (
            Path(state_path).resolve() if state_path else _default_state_path().resolve()
        )
        self._lock_path = self._state_path.with_suffix(self._state_path.suffix + ".lock")
        self._worker = worker_name or os.getenv("WORKER_NAME", "unknown")

    def _read(self):
        if not self._state_path.exists():
            return _default_state()
        try:
            raw = json.loads(self._state_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("state must be a mapping")

            calls = raw.get("calls")
            if not isinstance(calls, list):
                raise ValueError("calls must be a list")

            return {
                "calls": [float(timestamp) for timestamp in calls],
                "cooldown_until": float(raw.get("cooldown_until") or 0.0),
                "rate_limit_streak": int(raw.get("rate_limit_streak") or 0),
                "last_rate_limit_at": float(raw.get("last_rate_limit_at") or 0.0),
            }
        except (OSError, ValueError, TypeError) as exc:
            raise FyersRateLimitError("RATE_LIMIT_STATE_INVALID") from exc

    def _write(self, state):
        d = self._state_path.parent
        d.mkdir(parents=True, exist_ok=True)
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
        """Block until one aggregate FYERS REST permit is available."""
        del endpoint  # one account-wide budget; retained for compatibility

        while True:
            with _exclusive_file_lock(self._lock_path):
                now = time.time()
                state = self._read()
                calls = _prune(state["calls"], now)
                c = _counts(calls, now)
                cooldown_until = float(state.get("cooldown_until") or 0.0)

                if now < cooldown_until:
                    sleep_for = min(5.0, cooldown_until - now)
                elif c["sec"] >= _LIMITS["per_second"]:
                    recent = sorted(t for t in calls if t > now - _SECOND_BUCKET_SECONDS)
                    sleep_for = 1.05 - (now - recent[0]) if recent else 0.2
                elif c["min"] >= _LIMITS["per_minute"]:
                    recent = sorted(t for t in calls if t > now - _MINUTE_BUCKET_SECONDS)
                    sleep_for = min(5.0, 60.0 - (now - recent[0])) if recent else 1.0
                elif c["day"] >= _LIMITS["per_day"]:
                    sleep_for = 30.0
                else:
                    calls.append(now)
                    state["calls"] = calls
                    self._write(state)
                    return True

            time.sleep(max(0.1, sleep_for))

    def record_rate_limit(self, endpoint: str = "default"):
        """Record one provider-side 429 and apply a shared cooldown.

        The method deliberately does not retry the failed call.  The caller sees
        the original provider result/exception while every process observes the
        same cooldown before its next request.
        """
        del endpoint

        with _exclusive_file_lock(self._lock_path):
            now = time.time()
            state = self._read()
            state["calls"] = _prune(state["calls"], now)

            last = float(state.get("last_rate_limit_at") or 0.0)
            previous_streak = int(state.get("rate_limit_streak") or 0)
            if last and now - last <= _RATE_LIMIT_STREAK_WINDOW_SECONDS:
                streak = previous_streak + 1
            else:
                streak = 1

            cooldown = min(
                _RATE_LIMIT_MAX_COOLDOWN_SECONDS,
                _RATE_LIMIT_BASE_COOLDOWN_SECONDS * (2 ** (streak - 1)),
            )

            state["rate_limit_streak"] = streak
            state["last_rate_limit_at"] = now
            state["cooldown_until"] = max(
                float(state.get("cooldown_until") or 0.0),
                now + cooldown,
            )
            self._write(state)

            return cooldown

    def stats(self):
        now = time.time()
        with _exclusive_file_lock(self._lock_path):
            state = self._read()
            calls = _prune(state["calls"], now)
            result = _counts(calls, now)
            result.update(
                {
                    "cooldown_remaining": max(
                        0.0,
                        float(state.get("cooldown_until") or 0.0) - now,
                    ),
                    "rate_limit_streak": int(state.get("rate_limit_streak") or 0),
                }
            )
            return result


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
