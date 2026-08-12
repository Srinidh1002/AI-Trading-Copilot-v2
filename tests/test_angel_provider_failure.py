from __future__ import annotations

import pytest

from services.broker.angel_provider_failure import (
    classify_angel_provider_failure,
    is_angel_authentication_failure,
    is_angel_rate_limit_failure,
    is_valid_angel_provider_failure_kind,
)


class ProviderException(RuntimeError):
    def __init__(
        self,
        message,
        *,
        status_code=None,
        errorcode=None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.errorcode = errorcode


@pytest.mark.parametrize(
    ("error_code", "expected"),
    (
        ("AG8001", "AUTH_INVALID"),
        ("AG8002", "AUTH_EXPIRED"),
        ("AG8003", "AUTH_INVALID"),
        ("AB8050", "AUTH_INVALID"),
        ("AB8051", "AUTH_EXPIRED"),
        ("AB1010", "SESSION_EXPIRED"),
        ("AB1011", "SESSION_EXPIRED"),
        ("AB1009", "SYMBOL_INVALID"),
        ("AB1018", "SYMBOL_LOOKUP_FAILED"),
        ("AB1004", "PROVIDER_TRANSIENT"),
        ("AB2001", "PROVIDER_INTERNAL"),
        ("AB2000", "UNKNOWN_PROVIDER_ERROR"),
        ("AB1021", "RATE_LIMIT"),
    ),
)
def test_documented_angel_error_codes_are_normalized(
    error_code,
    expected,
):
    assert classify_angel_provider_failure(
        response={
            "status": False,
            "message": "provider failure",
            "errorcode": error_code,
            "data": None,
        }
    ) == expected


def test_documented_rate_limit_message_wins_over_http_403():
    exception = ProviderException(
        "Access denied because of exceeding rate limit",
        status_code=403,
    )

    assert classify_angel_provider_failure(
        exception=exception,
    ) == "RATE_LIMIT"


def test_bare_http_403_is_not_assumed_to_be_rate_limit():
    exception = ProviderException(
        "Forbidden",
        status_code=403,
    )

    assert classify_angel_provider_failure(
        exception=exception,
    ) == "UNKNOWN_PROVIDER_ERROR"


def test_http_403_with_token_expired_message_is_auth_expired():
    exception = ProviderException(
        "Authorization token is expired",
        status_code=403,
    )

    assert classify_angel_provider_failure(
        exception=exception,
    ) == "AUTH_EXPIRED"


def test_http_429_is_rate_limit():
    exception = ProviderException(
        "Provider rejected request",
        status_code=429,
    )

    assert classify_angel_provider_failure(
        exception=exception,
    ) == "RATE_LIMIT"


def test_http_401_is_auth_invalid():
    exception = ProviderException(
        "Unauthorized",
        status_code=401,
    )

    assert classify_angel_provider_failure(
        exception=exception,
    ) == "AUTH_INVALID"


def test_success_envelope_is_never_failure_classified():
    assert classify_angel_provider_failure(
        response={
            "status": True,
            "message": "SUCCESS",
            "errorcode": "",
            "data": {
                "http_code": 403,
            },
        }
    ) == "NONE"


def test_transient_network_failure_is_normalized():
    assert classify_angel_provider_failure(
        exception=RuntimeError(
            "Connection reset by peer"
        )
    ) == "PROVIDER_TRANSIENT"


@pytest.mark.parametrize(
    "value",
    (
        "AUTH_INVALID",
        "AUTH_EXPIRED",
        "SESSION_EXPIRED",
    ),
)
def test_authentication_helper_accepts_only_auth_classes(
    value,
):
    assert is_angel_authentication_failure(value) is True


def test_rate_limit_helper_is_exact():
    assert is_angel_rate_limit_failure("RATE_LIMIT") is True
    assert is_angel_rate_limit_failure("AUTH_EXPIRED") is False


def test_every_returned_classification_is_declared():
    values = (
        classify_angel_provider_failure(
            response={
                "status": False,
                "message": "Symbol not found",
                "errorcode": "AB1009",
            }
        ),
        classify_angel_provider_failure(
            exception=RuntimeError(
                "unknown provider failure"
            )
        ),
    )

    assert all(
        is_valid_angel_provider_failure_kind(value)
        for value in values
    )
