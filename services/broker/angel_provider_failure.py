"""Normalized Angel One provider failure classification."""
from __future__ import annotations

from collections.abc import Mapping


_PROVIDER_FAILURE_KINDS = {
    "NONE",
    "RATE_LIMIT",
    "AUTH_INVALID",
    "AUTH_EXPIRED",
    "SESSION_EXPIRED",
    "SYMBOL_INVALID",
    "SYMBOL_LOOKUP_FAILED",
    "PROVIDER_TRANSIENT",
    "PROVIDER_INTERNAL",
    "UNKNOWN_PROVIDER_ERROR",
}

_RATE_LIMIT_CODES = {
    "AB1021",
}

_AUTH_INVALID_CODES = {
    "AG8001",
    "AG8003",
    "AB8050",
}

_AUTH_EXPIRED_CODES = {
    "AG8002",
    "AB8051",
}

_SESSION_EXPIRED_CODES = {
    "AB1010",
    "AB1011",
}

_SYMBOL_INVALID_CODES = {
    "AB1009",
}

_SYMBOL_LOOKUP_FAILED_CODES = {
    "AB1018",
}

_PROVIDER_TRANSIENT_CODES = {
    "AB1004",
}

_PROVIDER_INTERNAL_CODES = {
    "AB2001",
}

_UNKNOWN_PROVIDER_CODES = {
    "AB2000",
}

_RATE_LIMIT_TERMS = (
    "exceeding access rate",
    "exceeding rate limit",
    "access rate exceeded",
    "rate limit exceeded",
    "rate limited",
    "rate_limited",
    "too many requests",
    "too many request",
)

_AUTH_INVALID_TERMS = (
    "invalid auth token",
    "invalid token",
    "token missing",
    "invalid refresh token",
    "unauthorized",
    "authentication failed",
)

_AUTH_EXPIRED_TERMS = (
    "token expired",
    "refresh token expired",
    "jwt expired",
    "authorization token is expired",
    "authorization_token is expired",
)

_SESSION_EXPIRED_TERMS = (
    "session expired",
    "invalid session",
    "client not login",
    "client not logged in",
)

_TRANSIENT_TERMS = (
    "timed out",
    "timeout",
    "temporarily unavailable",
    "temporary failure",
    "service unavailable",
    "connection reset",
    "connection aborted",
    "connection refused",
    "bad gateway",
    "gateway timeout",
    "max retries exceeded",
)

_INTERNAL_TERMS = (
    "internal server error",
    "internal error",
)


def _normalize_error_code(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip().upper()


def _response_status_is_success(
    response: object,
) -> bool:
    if not isinstance(response, Mapping):
        return False

    if "status" in response:
        value = response.get("status")
    elif "success" in response:
        value = response.get("success")
    else:
        return False

    if value is True:
        return True

    if isinstance(value, str):
        return value.strip().lower() in {
            "true",
            "success",
            "successful",
        }

    return False


def _response_error_code(
    response: object,
) -> str:
    if not isinstance(response, Mapping):
        return ""

    return _normalize_error_code(
        response.get(
            "errorcode",
            response.get(
                "errorCode",
                "",
            ),
        )
    )


def _status_code_from_object(
    value: object,
) -> int | None:
    for attribute in (
        "status_code",
        "statusCode",
    ):
        raw = getattr(
            value,
            attribute,
            None,
        )

        if isinstance(raw, int) and not isinstance(
            raw,
            bool,
        ):
            return raw

        if isinstance(raw, str):
            cleaned = raw.strip()
            if cleaned.isdigit():
                return int(cleaned)

    return None


def _classification_from_code(
    error_code: str,
) -> str | None:
    if error_code in _RATE_LIMIT_CODES:
        return "RATE_LIMIT"

    if error_code in _AUTH_INVALID_CODES:
        return "AUTH_INVALID"

    if error_code in _AUTH_EXPIRED_CODES:
        return "AUTH_EXPIRED"

    if error_code in _SESSION_EXPIRED_CODES:
        return "SESSION_EXPIRED"

    if error_code in _SYMBOL_INVALID_CODES:
        return "SYMBOL_INVALID"

    if error_code in _SYMBOL_LOOKUP_FAILED_CODES:
        return "SYMBOL_LOOKUP_FAILED"

    if error_code in _PROVIDER_TRANSIENT_CODES:
        return "PROVIDER_TRANSIENT"

    if error_code in _PROVIDER_INTERNAL_CODES:
        return "PROVIDER_INTERNAL"

    if error_code in _UNKNOWN_PROVIDER_CODES:
        return "UNKNOWN_PROVIDER_ERROR"

    return None


def _classification_from_text(
    text: str,
) -> str | None:
    normalized = text.lower()

    if any(
        term in normalized
        for term in _RATE_LIMIT_TERMS
    ):
        return "RATE_LIMIT"

    if any(
        term in normalized
        for term in _AUTH_EXPIRED_TERMS
    ):
        return "AUTH_EXPIRED"

    if any(
        term in normalized
        for term in _SESSION_EXPIRED_TERMS
    ):
        return "SESSION_EXPIRED"

    if any(
        term in normalized
        for term in _AUTH_INVALID_TERMS
    ):
        return "AUTH_INVALID"

    if any(
        term in normalized
        for term in _INTERNAL_TERMS
    ):
        return "PROVIDER_INTERNAL"

    if any(
        term in normalized
        for term in _TRANSIENT_TERMS
    ):
        return "PROVIDER_TRANSIENT"

    return None


def classify_angel_provider_failure(
    *,
    response: object = None,
    exception: BaseException | None = None,
) -> str:
    """Return one normalized Angel provider failure kind.

    HTTP 403 is intentionally not sufficient by itself to classify
    rate limiting because Angel documents 403 for both REST rate-limit
    failures and some expired-authorization paths.
    """

    if (
        response is not None
        and _response_status_is_success(response)
    ):
        return "NONE"

    error_code = _response_error_code(
        response
    )

    by_code = _classification_from_code(
        error_code
    )
    if by_code is not None:
        return by_code

    text_parts: list[str] = []

    if isinstance(response, Mapping):
        text_parts.extend(
            (
                str(response.get("message", "")),
                error_code,
                str(
                    response.get(
                        "statusCode",
                        response.get(
                            "status_code",
                            "",
                        ),
                    )
                ),
            )
        )

    status_codes: list[int] = []

    current = exception
    visited: set[int] = set()

    while (
        current is not None
        and id(current) not in visited
    ):
        visited.add(id(current))

        text_parts.append(str(current))

        exception_code = _normalize_error_code(
            getattr(
                current,
                "errorcode",
                getattr(
                    current,
                    "errorCode",
                    "",
                ),
            )
        )

        by_code = _classification_from_code(
            exception_code
        )
        if by_code is not None:
            return by_code

        status_code = _status_code_from_object(
            current
        )
        if status_code is not None:
            status_codes.append(status_code)

        response_value = getattr(
            current,
            "response",
            None,
        )

        if response_value is not None:
            text_parts.append(
                str(response_value)
            )

            response_status_code = (
                _status_code_from_object(
                    response_value
                )
            )

            if response_status_code is not None:
                status_codes.append(
                    response_status_code
                )

        current = (
            current.__cause__
            if current.__cause__ is not None
            else current.__context__
        )

    combined = " ".join(
        text_parts
    )

    by_text = _classification_from_text(
        combined
    )
    if by_text is not None:
        return by_text

    if 429 in status_codes:
        return "RATE_LIMIT"

    if 401 in status_codes:
        return "AUTH_INVALID"

    if any(
        status >= 500
        for status in status_codes
    ):
        return "PROVIDER_TRANSIENT"

    # Deliberately ambiguous:
    # bare HTTP 403 may mean rate limit or expired authorization.
    if 403 in status_codes:
        return "UNKNOWN_PROVIDER_ERROR"

    return "UNKNOWN_PROVIDER_ERROR"


def is_angel_authentication_failure(
    classification: object,
) -> bool:
    """Return whether classification requires session recovery."""

    if not isinstance(classification, str):
        return False

    return classification.strip().upper() in {
        "AUTH_INVALID",
        "AUTH_EXPIRED",
        "SESSION_EXPIRED",
    }


def is_angel_rate_limit_failure(
    classification: object,
) -> bool:
    """Return whether classification is an Angel rate-limit failure."""

    return (
        isinstance(classification, str)
        and classification.strip().upper()
        == "RATE_LIMIT"
    )


def is_valid_angel_provider_failure_kind(
    value: object,
) -> bool:
    """Return whether value is a known normalized classification."""

    return (
        isinstance(value, str)
        and value.strip().upper()
        in _PROVIDER_FAILURE_KINDS
    )
