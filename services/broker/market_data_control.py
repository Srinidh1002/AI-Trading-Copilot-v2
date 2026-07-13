"""Centralized controls for read-only broker market-data requests.

Values are operational defaults, not statements of Angel One's undocumented
limits. Deployments can tune every pacing and cooldown value through env vars.
"""

from copy import deepcopy
import logging
import os
import threading
import time


LOGGER = logging.getLogger(__name__)


def _non_negative_float(value, name):
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric.") from exc
    if value < 0:
        raise ValueError(f"{name} cannot be negative.")
    return value


def configured_value(name, default, cast, value=None):
    raw = os.getenv(name, str(default)) if value is None else value
    if isinstance(raw, bool):
        raise ValueError(f"{name} must be numeric.")
    try:
        parsed = cast(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric.") from exc
    if parsed < 0:
        raise ValueError(f"{name} cannot be negative.")
    return parsed


class BrokerMarketDataRequestError(RuntimeError):
    """Failed live-data request with structured, fail-closed context."""

    def __init__(self, request_name, attempts, failure_type, detail):
        self.failure = {
            "request_name": request_name,
            "attempts": attempts,
            "failure_type": failure_type,
            "detail": str(detail),
        }
        super().__init__(
            f"Angel One {request_name} {failure_type} after "
            f"{attempts} attempts: {detail}"
        )


class MarketDataRequestController:
    """Serializes requests, applies endpoint pacing, and caches valid data."""

    def __init__(
        self,
        *,
        min_request_interval_seconds=None,
        historical_request_interval_seconds=None,
        cache_ttl_seconds=None,
        rate_limit_cooldown_seconds=None,
        monotonic_function=time.monotonic,
        sleep_function=time.sleep,
    ):
        self.min_request_interval_seconds = _non_negative_float(
            configured_value(
                "ANGEL_MARKET_DATA_MIN_REQUEST_INTERVAL_SECONDS", 1.0, float,
                min_request_interval_seconds,
            ),
            "min_request_interval_seconds",
        )
        self.historical_request_interval_seconds = _non_negative_float(
            configured_value(
                "ANGEL_HISTORICAL_DATA_MIN_REQUEST_INTERVAL_SECONDS", 5.0, float,
                historical_request_interval_seconds,
            ),
            "historical_request_interval_seconds",
        )
        self.cache_ttl_seconds = _non_negative_float(
            configured_value("ANGEL_MARKET_DATA_CACHE_TTL_SECONDS", 2.0, float,
                             cache_ttl_seconds),
            "cache_ttl_seconds",
        )
        self.rate_limit_cooldown_seconds = _non_negative_float(
            configured_value("ANGEL_MARKET_DATA_RATE_LIMIT_COOLDOWN_SECONDS", 20.0,
                             float, rate_limit_cooldown_seconds),
            "rate_limit_cooldown_seconds",
        )
        self.monotonic_function = monotonic_function
        self.sleep_function = sleep_function
        self._lock = threading.Lock()
        self._last_request_at = None
        self._last_request_by_type = {}
        self._cooldown_until = 0.0
        self._cache = {}

    def _endpoint_interval(self, request_type):
        if request_type == "historical-data":
            return max(
                self.min_request_interval_seconds,
                self.historical_request_interval_seconds,
            )
        return self.min_request_interval_seconds

    def get_cached(self, key, request_type):
        now = self.monotonic_function()
        if self.cache_ttl_seconds == 0:
            LOGGER.info(
                "broker_request request_type=%s monotonic=%.6f cache=miss cache_disabled=true",
                request_type, now,
            )
            return None
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                LOGGER.info(
                    "broker_request request_type=%s monotonic=%.6f cache=miss",
                    request_type, now,
                )
                return None
            cached_at, response = entry
            if now - cached_at > self.cache_ttl_seconds:
                self._cache.pop(key, None)
                LOGGER.info(
                    "broker_request request_type=%s monotonic=%.6f cache=miss cache_expired=true",
                    request_type, now,
                )
                return None
            LOGGER.info(
                "broker_request request_type=%s monotonic=%.6f cache=hit",
                request_type, now,
            )
            return deepcopy(response)

    def cache(self, key, response):
        if self.cache_ttl_seconds:
            with self._lock:
                self._cache[key] = (self.monotonic_function(), deepcopy(response))

    def wait_for_slot(self, request_type, attempt):
        """Apply global, endpoint, and broker-cooldown pacing atomically."""
        with self._lock:
            now = self.monotonic_function()
            waits = [max(0.0, self._cooldown_until - now)]
            if self._last_request_at is not None:
                waits.append(max(
                    0.0,
                    self._endpoint_interval(request_type) - (
                        now - self._last_request_at
                    ),
                ))
            endpoint_last = self._last_request_by_type.get(request_type)
            if endpoint_last is not None:
                waits.append(max(
                    0.0,
                    self._endpoint_interval(request_type) - (now - endpoint_last),
                ))
            wait_seconds = max(waits)
            if wait_seconds > 0:
                self.sleep_function(wait_seconds)
            sent_at = self.monotonic_function()
            self._last_request_at = sent_at
            self._last_request_by_type[request_type] = sent_at
            LOGGER.info(
                "broker_request request_type=%s monotonic=%.6f attempt=%s wait_applied_seconds=%.6f",
                request_type, sent_at, attempt, wait_seconds,
            )
            return wait_seconds

    def record_rate_limit(self, request_type, retry_number, backoff_multiplier):
        """Start a global cooldown before any controlled broker retry."""
        now = self.monotonic_function()
        cooldown = self.rate_limit_cooldown_seconds * (
            float(backoff_multiplier) ** max(0, retry_number - 1)
        )
        with self._lock:
            self._cooldown_until = max(self._cooldown_until, now + cooldown)
        LOGGER.warning(
            "broker_request request_type=%s monotonic=%.6f rate_limited=true "
            "retry_number=%s cooldown_seconds=%.6f",
            request_type, now, retry_number, cooldown,
        )
        return cooldown

    def mark_request_complete(self, request_type):
        """Move the pacing boundary to completion of a multi-call SDK action."""
        completed_at = self.monotonic_function()
        with self._lock:
            self._last_request_at = completed_at
            self._last_request_by_type[request_type] = completed_at
        LOGGER.info(
            "broker_request request_type=%s monotonic=%.6f completed=true",
            request_type, completed_at,
        )
