"""Worker heartbeat emitter — Phase 5 of F15-R1.

PAPER-only. Best-effort. Never raises into the trading loop.

One atomic JSON heartbeat per market worker:
    <heartbeat_dir>/<MARKET>.json

Path resolution:
    1. If env PAPER_HEARTBEAT_DIR is set, use it.
    2. Else derive from module location: <repo_root>/logs/supervisor/heartbeats
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA_VERSION = 1
IST = timezone(timedelta(hours=5, minutes=30))

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DIR = _REPO_ROOT / "logs" / "supervisor" / "heartbeats"

_WARNED: set[str] = set()

# R22_HEARTBEAT_REPLACE_RETRY — OneDrive/Windows can transiently hold
# the destination of os.replace(). Retry PermissionError only; other
# filesystem failures retain the existing best-effort behavior.
_REPLACE_MAX_ATTEMPTS = 6
_REPLACE_BASE_DELAY_SECONDS = 0.05
_REPLACE_MAX_DELAY_SECONDS = 0.40


def _replace_with_permission_retry(source, target) -> None:
    for attempt in range(_REPLACE_MAX_ATTEMPTS):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt + 1 >= _REPLACE_MAX_ATTEMPTS:
                raise

            delay = min(
                _REPLACE_BASE_DELAY_SECONDS * (2 ** attempt),
                _REPLACE_MAX_DELAY_SECONDS,
            )

            time.sleep(delay)


def _heartbeat_dir() -> Path:
    override = os.environ.get("PAPER_HEARTBEAT_DIR")
    if override:
        return Path(override)
    return _DEFAULT_DIR


def _now_iso() -> str:
    return datetime.now(IST).isoformat(timespec="seconds")


def _read_existing(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def beat(
    market: str,
    stage: str,
    *,
    cycle_number: int | None = None,
    has_active_position: bool = False,
    trade_id: str | None = None,
    worker_generation: int | None = None,
) -> None:
    """Write one heartbeat for `market`. Best-effort; never raises."""
    path = None
    try:
        d = _heartbeat_dir()
        d.mkdir(parents=True, exist_ok=True)
        path = d / (market.upper() + ".json")

        now = _now_iso()
        prev = _read_existing(path)
        stage_u = stage.upper()

        if stage_u == "SLEEP":
            last_completed = now
        else:
            last_completed = prev.get("last_cycle_completed_at")

        if prev.get("stage") == stage_u:
            stage_started = prev.get("stage_started_at") or now
        else:
            stage_started = now

        gen = worker_generation
        if gen is None:
            env_gen = os.environ.get("PAPER_WORKER_GENERATION")
            if env_gen is not None:
                try:
                    gen = int(env_gen)
                except ValueError:
                    gen = None
            if gen is None:
                gen = prev.get("worker_generation")

        cyc = cycle_number if cycle_number is not None else prev.get("cycle_number")

        payload = {
            "schema_version": SCHEMA_VERSION,
            "market": market.upper(),
            "pid": os.getpid(),
            "worker_generation": gen,
            "timestamp": now,
            "cycle_number": cyc,
            "stage": stage_u,
            "stage_started_at": stage_started,
            "last_cycle_completed_at": last_completed,
            "has_active_position": bool(has_active_position),
            "trade_id": trade_id,
            "execution_mode": "PAPER",
        }

        fd, tmp = tempfile.mkstemp(
            prefix="." + path.name + ".", suffix=".tmp", dir=str(d)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, default=str)
                f.flush()
                os.fsync(f.fileno())
            _replace_with_permission_retry(tmp, path)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception as exc:
        key = str(path) if path else "?"
        if key not in _WARNED:
            _WARNED.add(key)
            try:
                print("  [heartbeat write skipped: "
                      + type(exc).__name__ + ": " + str(exc) + "]")
            except Exception:
                pass
