"""X1 request controller.

Wraps the existing ``FyersRateLimitCoordinator`` as the single
authoritative budget for FYERS REST requests. It does not create a
competing limiter, does not authenticate, does not perform I/O, and is
not installed by default into any live runtime.

Contract:

* Satisfies ``ProviderRequestControllerV2`` structurally.
* ``acquire_permit`` consumes exactly one permit before the caller's
  request runs. Cache hits must be handled by the caller without
  entering this context.
* Bounded wait: a caller may set ``max_wait_seconds``. The controller
  passes it through to the coordinator, which raises
  ``FyersRateLimitError("RATE_LIMIT_WAIT_DEADLINE_EXCEEDED")`` on
  deadline without consuming a permit.
* Retry policy is explicit and conservative:
    - ``classify_failure`` returns RETRYABLE or TERMINAL.
    - ``should_retry`` returns True only if the failure is RETRYABLE
      and remaining attempts > 0.
    - The controller never retries indefinite classes of failures.

Provider limits used by the underlying coordinator are those already
declared in ``src/rate_limiter.py``. This module does not alter them.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from threading import RLock

from src.rate_limiter import (
    FyersRateLimitCoordinator,
    FyersRateLimitError,
)


class FailureClassV1(StrEnum):
    RETRYABLE = "RETRYABLE"
    TERMINAL = "TERMINAL"


class RequestControllerError(RuntimeError):
    """Controller failed closed before the provider request could run."""


@dataclass(frozen=True, slots=True)
class RetryDecisionV1:
    retry: bool
    reason_code: str
    backoff_seconds: float


class FyersRequestControllerV2Impl:
    """X1 concrete implementation of the request-controller contract."""

    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    def __init__(
        self,
        *,
        coordinator: FyersRateLimitCoordinator,
        max_wait_seconds: float = 30.0,
        max_attempts: int = 3,
        base_backoff_seconds: float = 0.5,
    ) -> None:
        if not isinstance(coordinator, FyersRateLimitCoordinator):
            raise TypeError(
                "coordinator must be FyersRateLimitCoordinator."
            )
        if (
            isinstance(max_wait_seconds, bool)
            or not isinstance(max_wait_seconds, (int, float))
            or max_wait_seconds <= 0
        ):
            raise ValueError(
                "max_wait_seconds must be a positive number."
            )
        if (
            not isinstance(max_attempts, int)
            or isinstance(max_attempts, bool)
            or max_attempts < 1
        ):
            raise ValueError("max_attempts must be a positive integer.")
        if (
            isinstance(base_backoff_seconds, bool)
            or not isinstance(base_backoff_seconds, (int, float))
            or base_backoff_seconds <= 0
        ):
            raise ValueError(
                "base_backoff_seconds must be a positive number."
            )
        self._coordinator = coordinator
        self._max_wait = float(max_wait_seconds)
        self._max_attempts = max_attempts
        self._base_backoff = float(base_backoff_seconds)
        self._lock = RLock()

    @property
    def coordinator(self) -> FyersRateLimitCoordinator:
        return self._coordinator

    # ---------- ProviderRequestControllerV2 protocol ----------

    def wait_for_slot(self, request_type, attempt):
        """Block until a permit is available, with a bounded wait.

        Returns 0.0 to preserve the existing protocol contract.
        Raises FyersRateLimitError on deadline.
        """
        del attempt
        try:
            self._coordinator.wait_if_needed(
                str(request_type),
                max_wait_seconds=self._max_wait,
            )
        except FyersRateLimitError:
            raise
        except Exception as exc:  # noqa: BLE001 - fail closed
            raise RequestControllerError(
                "RATE_LIMIT_AUTHORITY_UNAVAILABLE"
            ) from exc
        return 0.0

    def record_rate_limit(
        self,
        request_type,
        retry_number,
        backoff_multiplier,
    ):
        """Return bounded backoff for the given retry number."""
        del request_type
        if (
            isinstance(retry_number, bool)
            or not isinstance(retry_number, int)
            or retry_number < 0
        ):
            raise ValueError(
                "retry_number must be a non-negative integer."
            )
        if (
            isinstance(backoff_multiplier, bool)
            or not isinstance(
                backoff_multiplier, (int, float)
            )
            or backoff_multiplier <= 0
        ):
            raise ValueError(
                "backoff_multiplier must be a positive number."
            )
        # Exponential, capped. Cap prevents unbounded backoff.
        exponent = min(retry_number, 6)
        raw = self._base_backoff * (float(backoff_multiplier) ** exponent)
        return min(raw, 30.0)

    def record_success(self, request_type):
        del request_type
        return None

    # ---------- X1 extensions ----------

    @contextmanager
    def acquire_permit(
        self, request_type: str = "default", *, attempt: int = 0
    ) -> Iterator[None]:
        """Atomically consume one permit, then yield.

        No permit is consumed if the deadline is exceeded.
        """
        try:
            self._coordinator.wait_if_needed(
                str(request_type),
                max_wait_seconds=self._max_wait,
            )
        except FyersRateLimitError:
            raise
        except Exception as exc:  # noqa: BLE001 - fail closed
            raise RequestControllerError(
                "RATE_LIMIT_AUTHORITY_UNAVAILABLE"
            ) from exc
        del attempt
        yield

    @staticmethod
    def classify_failure(
        *,
        http_status: int | None = None,
        provider_reason_code: str | None = None,
        exception: BaseException | None = None,
    ) -> FailureClassV1:
        """Classify a failure as RETRYABLE or TERMINAL.

        Conservative default is TERMINAL. Only clearly transient
        conditions are RETRYABLE.
        """
        if http_status in (408, 425, 429, 500, 502, 503, 504):
            return FailureClassV1.RETRYABLE
        if provider_reason_code in (
            "RATE_LIMIT",
            "PROVIDER_TEMPORARY",
            "TIMEOUT",
            "CONNECTION_RESET",
        ):
            return FailureClassV1.RETRYABLE
        if exception is not None:
            name = type(exception).__name__
            if name in (
                "TimeoutError",
                "ConnectionResetError",
                "ConnectionError",
            ):
                return FailureClassV1.RETRYABLE
        return FailureClassV1.TERMINAL

    def should_retry(
        self,
        *,
        attempt: int,
        failure_class: FailureClassV1,
        now: float | None = None,
    ) -> RetryDecisionV1:
        """Return a bounded retry decision. Never retry indefinitely."""
        if attempt < 0:
            raise ValueError("attempt must be non-negative.")
        if not isinstance(failure_class, FailureClassV1):
            raise TypeError(
                "failure_class must be FailureClassV1."
            )
        if failure_class is FailureClassV1.TERMINAL:
            return RetryDecisionV1(
                retry=False,
                reason_code="TERMINAL_FAILURE",
                backoff_seconds=0.0,
            )
        remaining = self._max_attempts - (attempt + 1)
        if remaining <= 0:
            return RetryDecisionV1(
                retry=False,
                reason_code="RETRY_EXHAUSTED",
                backoff_seconds=0.0,
            )
        backoff = self.record_rate_limit(
            "retry",
            attempt,
            2.0,
        )
        del now
        return RetryDecisionV1(
            retry=True,
            reason_code="RETRY",
            backoff_seconds=backoff,
        )


__all__ = [
    "FailureClassV1",
    "FyersRequestControllerV2Impl",
    "RequestControllerError",
    "RetryDecisionV1",
]
