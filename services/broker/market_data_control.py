"""
Centralized controls for read-only broker market-data requests.

The controller enforces:
- global minimum request spacing;
- endpoint-specific spacing;
- rolling historical-data request budgets;
- endpoint-scoped provider rate-limit cooldowns;
- short-lived in-process response caching.

Read-only.
No broker order submission.
"""

from collections import deque
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
        raise ValueError(
            f"{name} must be numeric."
        ) from exc

    if value < 0:
        raise ValueError(
            f"{name} cannot be negative."
        )

    return value


def _non_negative_int(value, name):
    if isinstance(value, bool):
        raise ValueError(
            f"{name} must be an integer."
        )

    try:
        value = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{name} must be an integer."
        ) from exc

    if value < 0:
        raise ValueError(
            f"{name} cannot be negative."
        )

    return value


def configured_value(
    name,
    default,
    cast,
    value=None,
):
    raw = (
        os.getenv(name, str(default))
        if value is None
        else value
    )

    if isinstance(raw, bool):
        raise ValueError(
            f"{name} must be numeric."
        )

    try:
        parsed = cast(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{name} must be numeric."
        ) from exc

    if parsed < 0:
        raise ValueError(
            f"{name} cannot be negative."
        )

    return parsed


class BrokerMarketDataRequestError(RuntimeError):
    """Sanitized typed broker market-data failure."""

    def __init__(
        self,
        request_name,
        attempts,
        failure_type,
        detail,
        *,
        provider_failure_kind=None,
    ):
        if provider_failure_kind is not None:
            from services.broker.angel_provider_failure import (
                is_valid_angel_provider_failure_kind,
            )

            if not is_valid_angel_provider_failure_kind(
                provider_failure_kind
            ):
                raise ValueError("provider_failure_kind")

        self.failure = {
            "request_name": request_name,
            "attempts": attempts,
            "failure_type": failure_type,
            "detail": str(detail),
        }

        if provider_failure_kind is not None:
            self.failure["provider_failure_kind"] = (
                provider_failure_kind.strip().upper()
            )

        super().__init__(
            f"Angel One {request_name} "
            f"{failure_type} after "
            f"{attempts} attempts: {detail}"
        )


class MarketDataRequestController:
    """Thread-safe request pacing and rolling-budget controller."""

    HISTORICAL_REQUEST_TYPE = "historical-data"
    MARKET_QUOTE_REQUEST_TYPE = "market-data"

    def __init__(
        self,
        *,
        min_request_interval_seconds=None,
        historical_request_interval_seconds=None,
        market_quote_request_interval_seconds=None,
        historical_requests_per_second=None,
        historical_requests_per_minute=None,
        historical_requests_per_hour=None,
        cache_ttl_seconds=None,
        rate_limit_cooldown_seconds=None,
        monotonic_function=time.monotonic,
        sleep_function=time.sleep,
    ):
        self.min_request_interval_seconds = (
            _non_negative_float(
                configured_value(
                    "ANGEL_MARKET_DATA_MIN_REQUEST_INTERVAL_SECONDS",
                    1.0,
                    float,
                    min_request_interval_seconds,
                ),
                "min_request_interval_seconds",
            )
        )

        self.historical_request_interval_seconds = (
            _non_negative_float(
                configured_value(
                    "ANGEL_HISTORICAL_DATA_MIN_REQUEST_INTERVAL_SECONDS",
                    1.0,
                    float,
                    historical_request_interval_seconds,
                ),
                "historical_request_interval_seconds",
            )
        )

        self.market_quote_request_interval_seconds = (
            _non_negative_float(
                configured_value(
                    "ANGEL_MARKET_QUOTE_MIN_REQUEST_INTERVAL_SECONDS",
                    0.0,
                    float,
                    market_quote_request_interval_seconds,
                ),
                "market_quote_request_interval_seconds",
            )
        )

        self.historical_requests_per_second = (
            _non_negative_int(
                configured_value(
                    "ANGEL_HISTORICAL_DATA_REQUESTS_PER_SECOND",
                    1,
                    int,
                    historical_requests_per_second,
                ),
                "historical_requests_per_second",
            )
        )

        self.historical_requests_per_minute = (
            _non_negative_int(
                configured_value(
                    "ANGEL_HISTORICAL_DATA_REQUESTS_PER_MINUTE",
                    120,
                    int,
                    historical_requests_per_minute,
                ),
                "historical_requests_per_minute",
            )
        )

        self.historical_requests_per_hour = (
            _non_negative_int(
                configured_value(
                    "ANGEL_HISTORICAL_DATA_REQUESTS_PER_HOUR",
                    4000,
                    int,
                    historical_requests_per_hour,
                ),
                "historical_requests_per_hour",
            )
        )

        self.cache_ttl_seconds = (
            _non_negative_float(
                configured_value(
                    "ANGEL_MARKET_DATA_CACHE_TTL_SECONDS",
                    2.0,
                    float,
                    cache_ttl_seconds,
                ),
                "cache_ttl_seconds",
            )
        )

        self.rate_limit_cooldown_seconds = (
            _non_negative_float(
                configured_value(
                    "ANGEL_MARKET_DATA_RATE_LIMIT_COOLDOWN_SECONDS",
                    20.0,
                    float,
                    rate_limit_cooldown_seconds,
                ),
                "rate_limit_cooldown_seconds",
            )
        )

        if not callable(monotonic_function):
            raise TypeError(
                "monotonic_function"
            )

        if not callable(sleep_function):
            raise TypeError(
                "sleep_function"
            )

        self.monotonic_function = (
            monotonic_function
        )
        self.sleep_function = sleep_function

        self._lock = threading.Lock()

        self._last_request_at = None
        self._last_request_by_type = {}

        # Cooldowns are endpoint-scoped.  A historical provider throttle must
        # not delay live spot/FULL quote or option-Greeks evidence.
        self._cooldown_until = {}
        self._cache = {}

        self._historical_request_times = deque()

    def _endpoint_interval(
        self,
        request_type,
    ):
        if (
            request_type
            == self.HISTORICAL_REQUEST_TYPE
        ):
            return max(
                self.min_request_interval_seconds,
                self.historical_request_interval_seconds,
            )

        if request_type == self.MARKET_QUOTE_REQUEST_TYPE:
            return max(
                self.min_request_interval_seconds,
                self.market_quote_request_interval_seconds,
            )

        return self.min_request_interval_seconds

    @staticmethod
    def _prune_window(
        timestamps,
        *,
        now,
        window_seconds,
    ):
        cutoff = now - float(window_seconds)

        while (
            timestamps
            and timestamps[0] <= cutoff
        ):
            timestamps.popleft()

    @staticmethod
    def _rolling_window_wait(
        timestamps,
        *,
        now,
        window_seconds,
        request_limit,
    ):
        if request_limit == 0:
            return 0.0

        if len(timestamps) < request_limit:
            return 0.0

        oldest_counted_request = timestamps[
            len(timestamps) - request_limit
        ]

        return max(
            0.0,
            (
                oldest_counted_request
                + float(window_seconds)
                - now
            ),
        )

    def _historical_budget_wait(
        self,
        now,
    ):
        self._prune_window(
            self._historical_request_times,
            now=now,
            window_seconds=3600.0,
        )

        waits = (
            self._rolling_window_wait(
                self._historical_request_times,
                now=now,
                window_seconds=1.0,
                request_limit=(
                    self.historical_requests_per_second
                ),
            ),
            self._rolling_window_wait(
                self._historical_request_times,
                now=now,
                window_seconds=60.0,
                request_limit=(
                    self.historical_requests_per_minute
                ),
            ),
            self._rolling_window_wait(
                self._historical_request_times,
                now=now,
                window_seconds=3600.0,
                request_limit=(
                    self.historical_requests_per_hour
                ),
            ),
        )

        return max(waits)

    def _required_wait(
        self,
        request_type,
        now,
    ):
        waits = [
            max(
                0.0,
                self._cooldown_until.get(request_type, 0.0) - now,
            )
        ]

        endpoint_interval = (
            self._endpoint_interval(
                request_type
            )
        )

        if self._last_request_at is not None:
            waits.append(
                max(
                    0.0,
                    endpoint_interval
                    - (
                        now
                        - self._last_request_at
                    ),
                )
            )

        endpoint_last = (
            self._last_request_by_type.get(
                request_type
            )
        )

        if endpoint_last is not None:
            waits.append(
                max(
                    0.0,
                    endpoint_interval
                    - (
                        now
                        - endpoint_last
                    ),
                )
            )

        if (
            request_type
            == self.HISTORICAL_REQUEST_TYPE
        ):
            waits.append(
                self._historical_budget_wait(
                    now
                )
            )

        return max(waits)

    def get_cached(
        self,
        key,
        request_type,
    ):
        now = self.monotonic_function()

        if self.cache_ttl_seconds == 0:
            LOGGER.info(
                "broker_request "
                "request_type=%s "
                "monotonic=%.6f "
                "cache=miss "
                "cache_disabled=true",
                request_type,
                now,
            )
            return None

        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                LOGGER.info(
                    "broker_request "
                    "request_type=%s "
                    "monotonic=%.6f "
                    "cache=miss",
                    request_type,
                    now,
                )
                return None

            cached_at, response = entry

            if (
                now - cached_at
                > self.cache_ttl_seconds
            ):
                self._cache.pop(
                    key,
                    None,
                )
                LOGGER.info(
                    "broker_request "
                    "request_type=%s "
                    "monotonic=%.6f "
                    "cache=miss "
                    "cache_expired=true",
                    request_type,
                    now,
                )
                return None

            LOGGER.info(
                "broker_request "
                "request_type=%s "
                "monotonic=%.6f "
                "cache=hit",
                request_type,
                now,
            )

            return deepcopy(response)

    def cache(
        self,
        key,
        response,
    ):
        if self.cache_ttl_seconds:
            with self._lock:
                self._cache[key] = (
                    self.monotonic_function(),
                    deepcopy(response),
                )

    def wait_for_slot(
        self,
        request_type,
        attempt,
    ):
        with self._lock:
            total_wait_seconds = 0.0

            while True:
                now = self.monotonic_function()

                wait_seconds = self._required_wait(
                    request_type,
                    now,
                )

                if wait_seconds <= 0:
                    break

                self.sleep_function(
                    wait_seconds
                )
                total_wait_seconds += wait_seconds

            sent_at = self.monotonic_function()

            self._last_request_at = sent_at
            self._last_request_by_type[
                request_type
            ] = sent_at

            if (
                request_type
                == self.HISTORICAL_REQUEST_TYPE
            ):
                self._historical_request_times.append(
                    sent_at
                )

            LOGGER.info(
                "broker_request "
                "request_type=%s "
                "monotonic=%.6f "
                "attempt=%s "
                "wait_applied_seconds=%.6f",
                request_type,
                sent_at,
                attempt,
                total_wait_seconds,
            )

            return total_wait_seconds

    def record_rate_limit(
        self,
        request_type,
        retry_number,
        backoff_multiplier,
    ):
        now = self.monotonic_function()

        cooldown = (
            self.rate_limit_cooldown_seconds
            * (
                float(backoff_multiplier)
                ** max(
                    0,
                    retry_number - 1,
                )
            )
        )

        with self._lock:
            self._cooldown_until[request_type] = max(
                self._cooldown_until.get(request_type, 0.0),
                now + cooldown,
            )

        LOGGER.warning(
            "broker_request "
            "request_type=%s "
            "monotonic=%.6f "
            "rate_limited=true "
            "retry_number=%s "
            "cooldown_seconds=%.6f",
            request_type,
            now,
            retry_number,
            cooldown,
        )

        return cooldown

    def mark_request_complete(
        self,
        request_type,
    ):
        completed_at = (
            self.monotonic_function()
        )

        with self._lock:
            self._last_request_at = (
                completed_at
            )
            self._last_request_by_type[
                request_type
            ] = completed_at

        LOGGER.debug(
            "broker_request "
            "request_type=%s "
            "monotonic=%.6f "
            "completed=true",
            request_type,
            completed_at,
        )

    def record_success(
        self,
        request_type,
    ):
        with self._lock:
            self._cooldown_until[request_type] = 0.0

        LOGGER.debug(
            "broker_request "
            "request_type=%s "
            "success=true",
            request_type,
        )
