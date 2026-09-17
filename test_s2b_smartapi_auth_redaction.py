import logging
import sys

sys.path.insert(0, "src")

from smartapi_log_redaction import (
    SmartApiSecretRedactionFilter,
    install_smartapi_log_redaction,
    redact_text,
)


FAKES = (
    "FAKECLIENT_918273",
    "FAKEPIN_2846",
    "FAKETOTP_654321",
    "FAKE_REFRESH_TOKEN_ABC123",
    "FAKE_JWT_TOKEN_DEF456",
    "FAKE_FEED_TOKEN_GHI789",
    "FAKE_PRIVATE_KEY_JKL012",
    "FAKE_BEARER_TOKEN_MNO345",
)


def _assert_no_fake_secret(value):
    text = str(value)

    for secret in FAKES:
        assert secret not in text


def test_python_dict_auth_request_is_redacted():
    original = (
        "Request: "
        "{'clientcode': 'FAKECLIENT_918273', "
        "'password': 'FAKEPIN_2846', "
        "'totp': 'FAKETOTP_654321'}"
    )

    safe = redact_text(original)

    _assert_no_fake_secret(safe)

    assert safe.count("[REDACTED]") == 3
    assert "'clientcode':" in safe
    assert "'password':" in safe
    assert "'totp':" in safe


def test_json_auth_response_tokens_are_redacted():
    original = (
        '{"refreshToken":"FAKE_REFRESH_TOKEN_ABC123",'
        '"jwtToken":"FAKE_JWT_TOKEN_DEF456",'
        '"feedToken":"FAKE_FEED_TOKEN_GHI789"}'
    )

    safe = redact_text(original)

    _assert_no_fake_secret(safe)

    assert safe.count("[REDACTED]") == 3


def test_unquoted_alias_forms_are_redacted():
    original = (
        "clientCode=FAKECLIENT_918273 "
        "PIN=FAKEPIN_2846 "
        "TOTP=FAKETOTP_654321 "
        "refresh_token=FAKE_REFRESH_TOKEN_ABC123 "
        "jwt_token=FAKE_JWT_TOKEN_DEF456 "
        "feed_token=FAKE_FEED_TOKEN_GHI789"
    )

    safe = redact_text(original)

    _assert_no_fake_secret(safe)

    assert safe.count("[REDACTED]") == 6


def test_existing_header_protections_remain_intact():
    original = (
        "Headers: {"
        "'Authorization': 'Bearer FAKE_BEARER_TOKEN_MNO345', "
        "'X-PrivateKey': 'FAKE_PRIVATE_KEY_JKL012'"
        "}"
    )

    safe = redact_text(original)

    _assert_no_fake_secret(safe)

    assert "Bearer [REDACTED]" in safe
    assert "[REDACTED]" in safe


def test_exact_smartapi_exception_log_shape_is_safe():
    original = (
        "Error occurred while making a POST request. "
        "Headers: {'X-PrivateKey': 'FAKE_PRIVATE_KEY_JKL012'}, "
        "Request: {'clientcode': 'FAKECLIENT_918273', "
        "'password': 'FAKEPIN_2846', "
        "'totp': 'FAKETOTP_654321'}, "
        "Response: connection failed"
    )

    safe = redact_text(original)

    _assert_no_fake_secret(safe)


def test_exact_smartapi_status_false_log_shape_is_safe():
    original = (
        "Error occurred while making a POST request. "
        "Request: {'refreshToken': "
        "'FAKE_REFRESH_TOKEN_ABC123'}, "
        "Response: {'status': False, 'data': {"
        "'jwtToken': 'FAKE_JWT_TOKEN_DEF456', "
        "'feedToken': 'FAKE_FEED_TOKEN_GHI789'}}"
    )

    safe = redact_text(original)

    _assert_no_fake_secret(safe)


def test_debug_response_bytes_style_is_safe():
    original = (
        'Response: 200 b\'{"data":{'
        '"jwtToken":"FAKE_JWT_TOKEN_DEF456",'
        '"refreshToken":"FAKE_REFRESH_TOKEN_ABC123",'
        '"feedToken":"FAKE_FEED_TOKEN_GHI789"}}\''
    )

    safe = redact_text(original)

    _assert_no_fake_secret(safe)


def test_logging_filter_sanitizes_rendered_args():
    record = logging.LogRecord(
        name="logzero_default",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="SDK failure Request: %s",
        args=(
            {
                "clientcode": "FAKECLIENT_918273",
                "password": "FAKEPIN_2846",
                "totp": "FAKETOTP_654321",
            },
        ),
        exc_info=None,
    )

    filt = SmartApiSecretRedactionFilter()

    assert filt.filter(record) is True

    rendered = record.getMessage()

    _assert_no_fake_secret(rendered)

    assert record.args == ()


def test_installation_is_idempotent_on_logger_and_handler():
    logger = logging.getLogger(
        "logzero_default"
    )

    handler = logging.StreamHandler()

    logger.addHandler(handler)

    try:
        install_smartapi_log_redaction()
        install_smartapi_log_redaction()

        logger_filters = [
            f
            for f in logger.filters
            if isinstance(
                f,
                SmartApiSecretRedactionFilter,
            )
        ]

        handler_filters = [
            f
            for f in handler.filters
            if isinstance(
                f,
                SmartApiSecretRedactionFilter,
            )
        ]

        assert len(logger_filters) == 1
        assert len(handler_filters) == 1

    finally:
        logger.removeHandler(handler)


def test_non_secret_market_message_is_unchanged():
    original = (
        "Spot=23259.75 PCR=1.24 "
        "ACTION=WAIT"
    )

    assert redact_text(original) == original



def test_redaction_is_idempotent_for_existing_placeholders():
    samples = (
        "clientCode=[REDACTED]",
        "clientcode=[REDACTED]",
        "password=[REDACTED]",
        "PIN=[REDACTED]",
        "totp=[REDACTED]",
        "refreshToken=[REDACTED]",
        "refresh_token=[REDACTED]",
        "jwtToken=[REDACTED]",
        "jwt_token=[REDACTED]",
        "feedToken=[REDACTED]",
        "feed_token=[REDACTED]",
        "'clientcode': '[REDACTED]'",
        '"jwtToken":"[REDACTED]"',
        "Authorization: Bearer [REDACTED]",
        "X-PrivateKey: [REDACTED]",
    )

    for original in samples:
        once = redact_text(original)
        twice = redact_text(once)

        assert once == original
        assert twice == once


def test_redaction_output_reaches_fixed_point():
    originals = (
        (
            "Request: {'clientcode': 'FAKECLIENT_918273', "
            "'password': 'FAKEPIN_2846', "
            "'totp': 'FAKETOTP_654321'}"
        ),
        (
            '{"refreshToken":"FAKE_REFRESH_TOKEN_ABC123",'
            '"jwtToken":"FAKE_JWT_TOKEN_DEF456",'
            '"feedToken":"FAKE_FEED_TOKEN_GHI789"}'
        ),
        (
            "clientCode=FAKECLIENT_918273 "
            "password=FAKEPIN_2846 "
            "totp=FAKETOTP_654321"
        ),
    )

    for original in originals:
        once = redact_text(original)
        twice = redact_text(once)
        third = redact_text(twice)

        _assert_no_fake_secret(once)

        assert twice == once
        assert third == twice
