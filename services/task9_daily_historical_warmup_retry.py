"""Durable bounded retry authority for optional Task 9 daily history."""
from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path


MAX_ATTEMPTS = 4
BACKOFF_SECONDS = (300, 900, 1800)


class Task9DailyWarmupRetryStore:
    """One failure budget per market, token, and completed-daily identity."""

    VERSION = 1

    def __init__(self, file_path, *, time_function=time.time):
        self.file_path = Path(file_path)
        self.time_function = time_function

    def _read(self):
        if not self.file_path.exists():
            return {"version": self.VERSION, "entries": {}}
        try:
            value = json.loads(self.file_path.read_text(encoding="utf-8"))
            if (
                not isinstance(value, dict)
                or set(value) != {"version", "entries"}
                or value.get("version") != self.VERSION
                or type(value.get("entries")) is not dict
            ):
                raise ValueError
            for key, entry in value["entries"].items():
                self._validate_entry(key, entry)
            return value
        except (AttributeError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("TASK9_DAILY_HISTORICAL_RETRY_STATE_INVALID") from exc

    @staticmethod
    def _validate_entry(key, entry):
        expected = {
            "attempt_count", "exhausted", "failure_category",
            "failed_at_epoch_seconds", "next_attempt_at_epoch_seconds",
            "required_identity",
        }
        if (
            not isinstance(key, str)
            or not key.startswith("historical:ONE_DAY:")
            or not isinstance(entry, dict)
            or set(entry) != expected
            or not isinstance(entry["required_identity"], str)
            or not entry["required_identity"]
            or not key.endswith(f":{entry['required_identity']}")
            or type(entry["attempt_count"]) is not int
            or not 1 <= entry["attempt_count"] <= MAX_ATTEMPTS
            or type(entry["exhausted"]) is not bool
            or entry["exhausted"] != (entry["attempt_count"] == MAX_ATTEMPTS)
            or not isinstance(entry["failure_category"], str)
            or not entry["failure_category"]
        ):
            raise ValueError("TASK9_DAILY_HISTORICAL_RETRY_STATE_INVALID")
        for field in ("failed_at_epoch_seconds", "next_attempt_at_epoch_seconds"):
            timestamp = entry[field]
            if timestamp is None and field == "next_attempt_at_epoch_seconds":
                continue
            if type(timestamp) not in (int, float) or not math.isfinite(timestamp) or timestamp < 0:
                raise ValueError("TASK9_DAILY_HISTORICAL_RETRY_STATE_INVALID")
        if entry["exhausted"] != (entry["next_attempt_at_epoch_seconds"] is None):
            raise ValueError("TASK9_DAILY_HISTORICAL_RETRY_STATE_INVALID")
        if (
            entry["next_attempt_at_epoch_seconds"] is not None
            and entry["next_attempt_at_epoch_seconds"] < entry["failed_at_epoch_seconds"]
        ):
            raise ValueError("TASK9_DAILY_HISTORICAL_RETRY_STATE_INVALID")

    def _write(self, value):
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.file_path.with_name(self.file_path.name + ".tmp")
        try:
            with temporary.open("w", encoding="utf-8") as handle:
                json.dump(value, handle, sort_keys=True, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.file_path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def key(*, exchange, symboltoken, required_identity):
        return f"historical:ONE_DAY:{str(exchange).upper()}:{symboltoken}:{required_identity}"

    def status(self, *, exchange, symboltoken, required_identity):
        value = self._read()["entries"].get(self.key(exchange=exchange, symboltoken=symboltoken, required_identity=required_identity))
        if value is None:
            return None
        if value["required_identity"] != required_identity:
            raise ValueError("TASK9_DAILY_HISTORICAL_RETRY_STATE_INVALID")
        return dict(value)

    def record_failure(self, *, exchange, symboltoken, required_identity, failure_category, not_before_epoch_seconds=None):
        document = self._read()
        key = self.key(exchange=exchange, symboltoken=symboltoken, required_identity=required_identity)
        previous = document["entries"].get(key)
        attempts = 1 if previous is None else previous["attempt_count"] + 1
        attempts = min(attempts, MAX_ATTEMPTS)
        now = float(self.time_function())
        backoff = BACKOFF_SECONDS[min(attempts, 3) - 1] if attempts < MAX_ATTEMPTS else None
        next_at = None if backoff is None else now + backoff
        if (
            next_at is not None
            and not_before_epoch_seconds is not None
        ):
            next_at = max(
                next_at,
                float(not_before_epoch_seconds),
            )
        entry = {"attempt_count": attempts, "exhausted": attempts == MAX_ATTEMPTS, "failure_category": str(failure_category), "failed_at_epoch_seconds": now, "next_attempt_at_epoch_seconds": next_at, "required_identity": required_identity}
        document["entries"][key] = entry
        self._write(document)
        return dict(entry)

    def clear(self, *, exchange, symboltoken, required_identity):
        document = self._read()
        document["entries"].pop(self.key(exchange=exchange, symboltoken=symboltoken, required_identity=required_identity), None)
        self._write(document)
