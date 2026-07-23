"""
Centralized controls for read-only broker market-data requests.
"""

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

    def __init__(
        self,
        request_name,
        attempts,
        failure_type,
        detail,
    ):
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
                "ANGEL_MARKET_DATA_MIN_REQUEST_INTERVAL_SECONDS",
                1.0,
                float,
                min_request_interval_seconds,
            ),
            "min_request_interval_seconds",
        )

        self.historical_request_interval_seconds = _non_negative_float(
            configured_value(
                "ANGEL_HISTORICAL_DATA_MIN_REQUEST_INTERVAL_SECONDS",
                5.0,
                float,
                historical_request_interval_seconds,
            ),
            "historical_request_interval_seconds",
        )

        self.rate_limit_cooldown_seconds = _non_negative_float(
            configured_value(
                "ANGEL_MARKET_DATA_RATE_LIMIT_COOLDOWN_SECONDS",
                20.0,
                float,
                rate_limit_cooldown_seconds,
            ),
            "rate_limit_cooldown_seconds",
        )

        self.monotonic_function = monotonic_function
        self.sleep_function = sleep_function

        self._lock = threading.Lock()

        self._last_request_at = None
        self._last_request_by_type = {}

        self._cooldown_until = 0.0

    def _endpoint_interval(
        self,
        request_type,
    ):

        if request_type == "historical-data":
            return max(
                self.min_request_interval_seconds,
                self.historical_request_interval_seconds,
            )

        return self.min_request_interval_seconds

    def get_cached(
        self,
        key,
        request_type,
    ):
    
        return None

    def cache(
        self,
        key,
        response,
    ):
        return

    def wait_for_slot(
        self,
        request_type,
        attempt,
    ):

        with self._lock:

            now = self.monotonic_function()

            waits = [
                max(
                    0.0,
                    self._cooldown_until - now,
                )
            ]

            if self._last_request_at is not None:

                waits.append(
                    max(
                        0.0,
                        self._endpoint_interval(
                            request_type
                        )
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
                        self._endpoint_interval(
                            request_type
                        )
                        - (
                            now
                            - endpoint_last
                        ),
                    )
                )

            wait_seconds = max(
                waits
            )

            if wait_seconds > 0:
                self.sleep_function(
                    wait_seconds
                )

            sent_at = self.monotonic_function()

            self._last_request_at = sent_at

            self._last_request_by_type[
                request_type
            ] = sent_at

            LOGGER.debug(
                "broker_request request_type=%s monotonic=%.6f attempt=%s wait_applied_seconds=%.6f",
                request_type,
                sent_at,
                attempt,
                wait_seconds,
            )

            return wait_seconds

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
                float(
                    backoff_multiplier
                )
                ** max(
                    0,
                    retry_number - 1,
                )
            )
        )

        with self._lock:

            self._cooldown_until = max(
                self._cooldown_until,
                now + cooldown,
            )

        LOGGER.warning(
            "broker_request request_type=%s monotonic=%.6f rate_limited=true retry_number=%s cooldown_seconds=%.6f",
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

        completed_at = self.monotonic_function()

        with self._lock:

            self._last_request_at = completed_at

            self._last_request_by_type[
                request_type
            ] = completed_at

        LOGGER.debug(
            "broker_request request_type=%s monotonic=%.6f completed=true",
            request_type,
            completed_at,
        )

        
    def record_success(
        self,
        request_type,
    ):
        """
        Record a successful broker request.
        """

        with self._lock:
            self._cooldown_until = 0.0

        LOGGER.debug(
            "broker_request request_type=%s success=true",
            request_type,
        )