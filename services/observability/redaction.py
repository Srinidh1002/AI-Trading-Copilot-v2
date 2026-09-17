"""Bounded, non-mutating sanitizer for audit attributes."""
from __future__ import annotations
from collections.abc import Mapping
from typing import Any

REDACTED = "[REDACTED]"
_SECRET_KEYS = {"password", "passwd", "secret", "token", "api_key", "apikey", "access_key", "refresh_token", "authorization", "cookie", "session", "client_secret", "otp", "pin", "private_key"}
_VISIBLE = {"authorization_status", "execution_status"}

def sanitize_audit_value(value: Any, *, max_depth: int = 4, max_collection: int = 50, max_string: int = 512) -> Any:
    def clean(item: Any, depth: int) -> Any:
        if depth > max_depth: return "[MAX_DEPTH]"
        if item is None or isinstance(item, (bool, int, float)): return item
        if isinstance(item, str): return item[:max_string]
        if isinstance(item, bytes): return "[BYTES]"
        if isinstance(item, Mapping):
            result = {}
            for key in sorted(item, key=lambda key: key if isinstance(key, str) else type(key).__name__)[:max_collection]:
                name = key if isinstance(key, str) else "[NON_STRING_KEY]"
                folded = name.casefold()
                is_secret = any(secret in folded for secret in _SECRET_KEYS)
                result[name] = clean(item[key], depth + 1) if name in _VISIBLE or not is_secret else REDACTED
            return result
        if isinstance(item, (list, tuple)):
            return [clean(value, depth + 1) for value in item[:max_collection]]
        return f"[UNSUPPORTED:{type(item).__name__}]"
    return clean(value, 0)
