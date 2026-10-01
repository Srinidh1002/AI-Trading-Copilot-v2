"""X1 bounded endpoint cache for read-only REST responses.

Safety properties:

* Refuses to cache authentication / session / token endpoints.
* Never caches failed or malformed responses; the caller's fetch must
  signal success by returning a mapping.
* Keys include provider, endpoint and all request parameters, so FYERS
  and Angel data can never be mixed.
* Endpoint-specific TTLs, not a universal TTL.
* Bounded LRU capacity.
* In-flight dedup: identical concurrent requests share one fetch.
  Dedup uses per-key events; no global lock is held across the fetch.

This module performs no network I/O. The caller supplies a ``fetch``
callable.
"""
from __future__ import annotations

import json
import math
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

_AUTH_PREFIXES = (
    "auth",
    "authenticate",
    "session",
    "token",
    "login",
    "generate_session",
)


class EndpointCacheError(RuntimeError):
    """Cache configuration failure."""


class AuthEndpointNotCacheable(EndpointCacheError):
    """Attempted to cache an authentication endpoint."""


class EndpointCacheTimeout(EndpointCacheError):
    """Timed out waiting for an in-flight identical request."""


@dataclass(frozen=True, slots=True)
class CachedResponseV1:
    value: Mapping[str, object]
    provider: str
    endpoint: str
    params_key: str
    observed_at: datetime
    cached_at: datetime
    ttl_seconds: float
    is_cached: bool
    cache_age_seconds: float


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _normalise_endpoint(endpoint: str) -> str:
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ValueError("endpoint must be a non-empty string.")
    normalised = endpoint.strip().lower()
    if any(normalised.startswith(prefix) for prefix in _AUTH_PREFIXES):
        raise AuthEndpointNotCacheable(
            f"auth-like endpoint not cacheable: {endpoint!r}"
        )
    return normalised


def _params_key(params: Mapping[str, object]) -> str:
    if not isinstance(params, Mapping):
        raise TypeError("params must be a mapping.")
    return sha256(_canonical(dict(params)).encode("utf-8")).hexdigest()


def _cache_key(
    *, provider: str, endpoint: str, params_key: str
) -> str:
    return sha256(
        _canonical(
            {
                "provider": provider,
                "endpoint": endpoint,
                "params_key": params_key,
            }
        ).encode("utf-8")
    ).hexdigest()


class EndpointCacheV1:
    """Bounded LRU endpoint cache with in-flight dedup."""

    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    def __init__(
        self,
        *,
        max_entries: int = 1024,
        endpoint_ttl_seconds: Mapping[str, float] | None = None,
        default_ttl_seconds: float = 5.0,
        clock: Callable[[], float] | None = None,
        wall_clock: Callable[[], datetime] | None = None,
        inflight_timeout_seconds: float = 30.0,
    ) -> None:
        if (
            not isinstance(max_entries, int)
            or isinstance(max_entries, bool)
            or max_entries < 1
        ):
            raise ValueError("max_entries must be a positive integer.")
        if (
            isinstance(default_ttl_seconds, bool)
            or not isinstance(default_ttl_seconds, (int, float))
            or not math.isfinite(default_ttl_seconds)
            or default_ttl_seconds < 0
        ):
            raise ValueError(
                "default_ttl_seconds must be a non-negative number."
            )
        if endpoint_ttl_seconds is not None:
            if not isinstance(endpoint_ttl_seconds, Mapping):
                raise ValueError(
                    "endpoint_ttl_seconds must be a mapping."
                )
            for key, value in endpoint_ttl_seconds.items():
                if not isinstance(key, str) or not key.strip():
                    raise ValueError(
                        "endpoint_ttl_seconds keys must be strings."
                    )
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or value < 0
                ):
                    raise ValueError(
                        "endpoint_ttl_seconds values must be "
                        "non-negative numbers."
                    )
        if (
            isinstance(inflight_timeout_seconds, bool)
            or not isinstance(inflight_timeout_seconds, (int, float))
            or inflight_timeout_seconds <= 0
        ):
            raise ValueError(
                "inflight_timeout_seconds must be a positive number."
            )
        self._max_entries = max_entries
        self._ttl_by_endpoint = {
            str(k).strip().lower(): float(v)
            for k, v in (endpoint_ttl_seconds or {}).items()
        }
        self._default_ttl = float(default_ttl_seconds)
        self._clock = clock or time.monotonic
        self._wall = wall_clock or (
            lambda: datetime.now(UTC)
        )
        self._inflight_timeout = float(inflight_timeout_seconds)
        self._lock = threading.RLock()
        # key -> (CachedResponseV1, monotonic expiry)
        self._entries: OrderedDict[str, tuple[CachedResponseV1, float]] = (
            OrderedDict()
        )
        # key -> Event signalled when the in-flight loader finishes
        self._inflight: dict[str, threading.Event] = {}

    def ttl_for(self, endpoint: str) -> float:
        normalised = _normalise_endpoint(endpoint)
        return self._ttl_by_endpoint.get(normalised, self._default_ttl)

    def get(
        self,
        *,
        provider: str,
        endpoint: str,
        params: Mapping[str, object],
    ) -> CachedResponseV1 | None:
        key, _, _ = self._make_key(
            provider=provider, endpoint=endpoint, params=params
        )
        now = self._clock()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if now >= expires_at:
                self._entries.pop(key, None)
                return None
            self._entries.move_to_end(key)
            return value

    def get_or_fetch(
        self,
        *,
        provider: str,
        endpoint: str,
        params: Mapping[str, object],
        fetch: Callable[[], Mapping[str, object]],
        ttl_seconds: float | None = None,
    ) -> CachedResponseV1:
        key, params_key, endpoint_norm = self._make_key(
            provider=provider, endpoint=endpoint, params=params
        )
        ttl = (
            self.ttl_for(endpoint_norm)
            if ttl_seconds is None
            else float(ttl_seconds)
        )
        if not math.isfinite(ttl) or ttl < 0:
            raise ValueError("ttl_seconds must be non-negative.")

        cached = self._lookup(key)
        if cached is not None:
            return cached

        loader_event: threading.Event | None = None
        is_loader = False
        with self._lock:
            existing = self._inflight.get(key)
            if existing is None:
                loader_event = threading.Event()
                self._inflight[key] = loader_event
                is_loader = True
            else:
                loader_event = existing

        if not is_loader:
            if not loader_event.wait(self._inflight_timeout):
                raise EndpointCacheTimeout(
                    "ENDPOINT_CACHE_INFLIGHT_TIMEOUT"
                )
            cached = self._lookup(key)
            if cached is None:
                raise EndpointCacheError(
                    "ENDPOINT_CACHE_INFLIGHT_LOAD_FAILED"
                )
            return cached

        try:
            response = fetch()
            if not isinstance(response, Mapping):
                raise EndpointCacheError(
                    "ENDPOINT_CACHE_FETCH_NON_MAPPING"
                )
            wall = self._wall()
            if (
                not isinstance(wall, datetime)
                or wall.tzinfo is None
                or wall.utcoffset() is None
            ):
                raise EndpointCacheError(
                    "ENDPOINT_CACHE_WALL_CLOCK_INVALID"
                )
            cached_response = CachedResponseV1(
                value=dict(response),
                provider=provider,
                endpoint=endpoint_norm,
                params_key=params_key,
                observed_at=wall,
                cached_at=wall,
                ttl_seconds=ttl,
                is_cached=False,
                cache_age_seconds=0.0,
            )
            with self._lock:
                self._store(key, cached_response, ttl)
            return cached_response
        finally:
            with self._lock:
                self._inflight.pop(key, None)
            loader_event.set()

    def invalidate(
        self,
        *,
        provider: str,
        endpoint: str,
        params: Mapping[str, object],
    ) -> None:
        key, _, _ = self._make_key(
            provider=provider, endpoint=endpoint, params=params
        )
        with self._lock:
            self._entries.pop(key, None)

    def invalidate_provider(self, provider: str) -> int:
        with self._lock:
            to_remove = [
                key
                for key, (entry, _) in self._entries.items()
                if entry.provider == provider
            ]
            for key in to_remove:
                self._entries.pop(key, None)
            return len(to_remove)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "entries": len(self._entries),
                "inflight": len(self._inflight),
                "max_entries": self._max_entries,
                "default_ttl_seconds": self._default_ttl,
                "endpoint_ttls": dict(self._ttl_by_endpoint),
            }

    # ---------- internals ----------

    def _make_key(
        self,
        *,
        provider: str,
        endpoint: str,
        params: Mapping[str, object],
    ) -> tuple[str, str, str]:
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError("provider must be a non-empty string.")
        endpoint_norm = _normalise_endpoint(endpoint)
        params_key = _params_key(params)
        key = _cache_key(
            provider=provider.strip().upper(),
            endpoint=endpoint_norm,
            params_key=params_key,
        )
        return key, params_key, endpoint_norm

    def _lookup(self, key: str) -> CachedResponseV1 | None:
        now = self._clock()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if now >= expires_at:
                self._entries.pop(key, None)
                return None
            self._entries.move_to_end(key)
            age = now - (
                expires_at - value.ttl_seconds
            )
            if age < 0:
                age = 0.0
            return CachedResponseV1(
                value=dict(value.value),
                provider=value.provider,
                endpoint=value.endpoint,
                params_key=value.params_key,
                observed_at=value.observed_at,
                cached_at=value.cached_at,
                ttl_seconds=value.ttl_seconds,
                is_cached=True,
                cache_age_seconds=age,
            )

    def _store(
        self,
        key: str,
        entry: CachedResponseV1,
        ttl_seconds: float,
    ) -> None:
        expiry = self._clock() + ttl_seconds
        self._entries[key] = (entry, expiry)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)


__all__ = [
    "AuthEndpointNotCacheable",
    "CachedResponseV1",
    "EndpointCacheError",
    "EndpointCacheTimeout",
    "EndpointCacheV1",
]
