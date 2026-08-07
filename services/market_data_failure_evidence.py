"""Sanitized provider/request failure classification across exception chains."""
from __future__ import annotations

from collections.abc import Mapping


_RATE_LIMIT_TERMS = (
    "rate_limited",
    "rate limit",
    "too many requests",
    "exceeding access rate",
    "access rate exceeded",
    "ab1021",
)


def classify_market_data_exception(
    exception: BaseException,
) -> tuple[bool, str]:
    """Return provider-throttle classification and sanitized reason code."""

    if not isinstance(exception, BaseException):
        raise TypeError("exception")

    current: BaseException | None = exception
    visited: set[int] = set()

    while current is not None and id(current) not in visited:
        visited.add(id(current))

        failure = getattr(current, "failure", None)
        if isinstance(failure, Mapping):
            failure_type = str(
                failure.get("failure_type", "")
            ).strip().lower()

            request_name = (
                str(
                    failure.get(
                        "request_name",
                        "market-data",
                    )
                ).strip()
                or "market-data"
            )

            if failure_type == "rate_limited":
                return (
                    True,
                    f"{request_name.upper()}_RATE_LIMITED",
                )

            return (
                False,
                f"{request_name.upper()}_REQUEST_FAILED",
            )

        text = str(current).lower()
        if any(term in text for term in _RATE_LIMIT_TERMS):
            return True, "PROVIDER_RATE_LIMITED"

        current = (
            current.__cause__
            if current.__cause__ is not None
            else current.__context__
        )

    return False, "EXECUTION_EXCEPTION"


def is_market_data_failure_reason(reason: object) -> bool:
    """Return whether a sanitized code represents a provider request failure."""

    if not isinstance(reason, str):
        return False

    code = reason.strip().upper()
    return (
        code == "PROVIDER_RATE_LIMITED"
        or code.endswith("_RATE_LIMITED")
        or code.endswith("_REQUEST_FAILED")
    )
