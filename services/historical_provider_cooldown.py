"""Durable, sanitized cooldown state for Angel historical-data failures.

This is deliberately infrastructure scoped: it persists only a provider,
endpoint, sanitized failure code, and deterministic expiry.  It has no
credential, request, quote, or trade data and never applies to spot/options.
"""
from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path


class HistoricalProviderCooldown:
    SCHEMA_VERSION = 1
    PROVIDER = "ANGEL_ONE"
    ENDPOINT = "historical-data"

    def __init__(self, file_path, *, time_function=time.time):
        self.file_path = Path(file_path)
        if not callable(time_function):
            raise TypeError("time_function")
        self.time_function = time_function

    @staticmethod
    def _now(value):
        if isinstance(value, bool):
            raise ValueError("clock")
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("clock")
        return value

    def _read(self):
        if not self.file_path.exists():
            return None
        try:
            value = json.loads(self.file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if type(value) is not dict or set(value) != {
            "version", "provider", "endpoint", "reason", "expires_at_epoch_seconds",
        }:
            return None
        if value["version"] != self.SCHEMA_VERSION or value["provider"] != self.PROVIDER or value["endpoint"] != self.ENDPOINT:
            return None
        if type(value["reason"]) is not str or not value["reason"].strip():
            return None
        try:
            expires = self._now(value["expires_at_epoch_seconds"])
        except (TypeError, ValueError):
            return None
        return {**value, "expires_at_epoch_seconds": expires}

    def _write(self, value):
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.file_path.with_name(f"{self.file_path.name}.tmp")
        try:
            serialized = json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            with temporary.open("w", encoding="utf-8", newline="") as handle:
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.file_path)
        except Exception:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def active(self):
        value = self._read()
        if value is None:
            return None
        now = self._now(self.time_function())
        if value["expires_at_epoch_seconds"] <= now:
            try:
                self.file_path.unlink(missing_ok=True)
            except OSError:
                pass
            return None
        return {
            "provider": self.PROVIDER,
            "endpoint": self.ENDPOINT,
            "reason": value["reason"],
            "expires_at_epoch_seconds": value["expires_at_epoch_seconds"],
            "remaining_seconds": value["expires_at_epoch_seconds"] - now,
        }

    def record_rate_limit(self, *, reason, cooldown_seconds):
        code = str(reason).strip().upper()
        if not code or any(part in code.lower() for part in ("secret", "password", "authorization", "token")):
            raise ValueError("reason")
        duration = self._now(cooldown_seconds)
        now = self._now(self.time_function())
        existing = self._read()
        expires = now + duration
        if existing is not None:
            expires = max(expires, existing["expires_at_epoch_seconds"])
        value = {
            "version": self.SCHEMA_VERSION,
            "provider": self.PROVIDER,
            "endpoint": self.ENDPOINT,
            "reason": code,
            "expires_at_epoch_seconds": expires,
        }
        self._write(value)
        return self.active()
