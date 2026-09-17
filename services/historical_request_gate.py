"""Durable historical-only pacing gate shared by local repository processes."""
from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path


class HistoricalRequestGate:
    """Atomic create-lock gate; state contains timestamps only, never credentials."""

    def __init__(self, file_path, *, interval_seconds=1.0, stale_lock_seconds=30.0, time_function=time.time, sleep_function=time.sleep):
        self.file_path = Path(file_path)
        self.lock_path = self.file_path.with_name(self.file_path.name + ".lock")
        self.interval_seconds = float(interval_seconds)
        self.stale_lock_seconds = float(stale_lock_seconds)
        self.time_function = time_function
        self.sleep_function = sleep_function
        if self.interval_seconds <= 0 or self.stale_lock_seconds <= 0:
            raise ValueError("historical gate timing")

    def _read_next_allowed(self):
        if not self.file_path.exists():
            return 0.0
        try:
            value = json.loads(self.file_path.read_text(encoding="utf-8"))
            if set(value) != {"version", "endpoint", "next_allowed_epoch_seconds"} or value["version"] != 1 or value["endpoint"] != "historical-data":
                raise ValueError("invalid historical request gate state")
            result = float(value["next_allowed_epoch_seconds"])
            if not math.isfinite(result):
                raise ValueError("invalid historical request gate state")
            return result
        except (OSError, TypeError, KeyError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError("invalid historical request gate state") from exc

    def _acquire_lock(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                with self.lock_path.open("x", encoding="utf-8") as handle:
                    handle.write(str(self.time_function()))
                return
            except FileExistsError:
                try:
                    acquired_at = float(
                        self.lock_path.read_text(encoding="utf-8")
                    )
                    age = self.time_function() - acquired_at
                    if age > self.stale_lock_seconds:
                        self.lock_path.unlink()
                        continue
                except (OSError, ValueError):
                    raise ValueError("invalid historical request gate lock")
                self.sleep_function(0.05)

    def acquire(self):
        self._acquire_lock()
        try:
            now = float(self.time_function())
            wait_seconds = max(0.0, self._read_next_allowed() - now)
            if wait_seconds:
                self.sleep_function(wait_seconds)
                now = float(self.time_function())
            next_allowed = now + self.interval_seconds
            temporary = self.file_path.with_name(self.file_path.name + ".tmp")
            try:
                with temporary.open("w", encoding="utf-8", newline="") as handle:
                    handle.write(json.dumps({"version": 1, "endpoint": "historical-data", "next_allowed_epoch_seconds": next_allowed}, sort_keys=True, separators=(",", ":")))
                    handle.flush(); os.fsync(handle.fileno())
                os.replace(temporary, self.file_path)
            finally:
                temporary.unlink(missing_ok=True)
            return {"wait_seconds": wait_seconds, "next_allowed_epoch_seconds": next_allowed}
        finally:
            self.lock_path.unlink(missing_ok=True)
