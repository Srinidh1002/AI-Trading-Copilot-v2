from unittest.mock import MagicMock, patch

import pytest

from services.broker.angel_client import (
    AngelMarketDataClient,
)


def make_client(
    max_retries=3,
    retry_delay_seconds=0,
):
    """
    Create a client without making
    any real Angel One API calls.
    """

    with patch(
        "services.broker.angel_client.SmartConnect"
    ) as smart_connect:

        api = MagicMock()

        smart_connect.return_value = api

        client = AngelMarketDataClient(
            max_retries=max_retries,
            retry_delay_seconds=(
                retry_delay_seconds
            ),
        )

    client.api = api
    client.authenticated = True
    client.session = {
        "status": True,
    }

    return client, api


def successful_market_response():
    """
    Return a valid mocked Angel One
    market-data response.
    """

    return {
        "status": True,
        "message": "SUCCESS",
        "data": {
            "fetched": [
                {
                    "exchange": "NSE",
                    "symbolToken": "99926000",
                    "ltp": 24206.9,
                }
            ],
            "unfetched": [],
        },
    }


def test_market_data_succeeds_first_attempt():

    client, api = make_client()

    api.getMarketData.return_value = (
        successful_market_response()
    )

    result = client.get_market_data(
        mode="LTP",
        exchange_tokens={
            "NSE": [
                "99926000"
            ]
        },
    )

    assert result["status"] is True

    assert (
        result["data"]["fetched"][0]["ltp"]
        == 24206.9
    )

    api.getMarketData.assert_called_once()


def test_timeout_retries_then_succeeds():

    client, api = make_client(
        max_retries=3,
    )

    api.getMarketData.side_effect = [
        TimeoutError(
            "Connection timed out."
        ),
        successful_market_response(),
    ]

    result = client.get_market_data(
        mode="LTP",
        exchange_tokens={
            "NSE": [
                "99926000"
            ]
        },
    )

    assert result["status"] is True

    assert (
        api.getMarketData.call_count
        == 2
    )


def test_repeated_timeout_fails_safely():

    client, api = make_client(
        max_retries=3,
    )

    api.getMarketData.side_effect = (
        TimeoutError(
            "Connection timed out."
        )
    )

    with pytest.raises(
        RuntimeError,
        match="failed after 3 attempts",
    ):
        client.get_market_data(
            mode="LTP",
            exchange_tokens={
                "NSE": [
                    "99926000"
                ]
            },
        )

    assert (
        api.getMarketData.call_count
        == 3
    )


def test_provider_failure_redacts_credential_like_values_from_logs_and_error(caplog, capsys):
    client, api = make_client(max_retries=1)
    secret = "api-key-secret jwt-secret refresh-secret feed-secret pin-secret totp-secret"
    api.getCandleData.side_effect = TimeoutError(
        "timed out headers={'X-PrivateKey': 'api-key-secret', 'Authorization': 'Bearer jwt-secret', 'Cookie': 'refresh-secret'} " + secret
    )
    with pytest.raises(RuntimeError) as error:
        client.get_historical_data("NSE", "99926000", "FIVE_MINUTE", "2026-08-03 09:00", "2026-08-03 10:00")
    rendered = "\n".join((str(error.value), capsys.readouterr().out, capsys.readouterr().err, *(record.getMessage() for record in caplog.records)))
    for value in ("api-key-secret", "jwt-secret", "refresh-secret", "feed-secret", "pin-secret", "totp-secret"):
        assert value not in rendered
    assert "historical-data" in rendered


def test_authentication_failure_reauthenticates():

    client, api = make_client(
        max_retries=3,
    )

    api.getMarketData.side_effect = [
        {
            "status": False,
            "message": "Token expired",
        },
        successful_market_response(),
    ]

    def mock_login(
        force=False,
    ):
        """
        Simulate the state changes performed
        by the real login method.
        """

        client.authenticated = True

        client.session = {
            "status": True,
        }

        return client.session

    client.login = MagicMock(
        side_effect=mock_login
    )

    result = client.get_market_data(
        mode="LTP",
        exchange_tokens={
            "NSE": [
                "99926000"
            ]
        },
    )

    assert result["status"] is True

    client.login.assert_called_once_with(
        force=True
    )

    assert (
        client.authenticated
        is True
    )

    assert (
        api.getMarketData.call_count
        == 2
    )


def test_non_retryable_error_stops_immediately():

    client, api = make_client(
        max_retries=3,
    )

    api.getMarketData.side_effect = (
        ValueError(
            "Invalid request."
        )
    )

    with pytest.raises(
        ValueError,
        match="Invalid request",
    ):
        client.get_market_data(
            mode="LTP",
            exchange_tokens={
                "NSE": [
                    "99926000"
                ]
            },
        )

    api.getMarketData.assert_called_once()


def test_empty_response_is_rejected():

    client, api = make_client()

    api.getMarketData.return_value = None

    with pytest.raises(
        RuntimeError,
        match="empty market-data response",
    ):
        client.get_market_data(
            mode="LTP",
            exchange_tokens={
                "NSE": [
                    "99926000"
                ]
            },
        )


@pytest.mark.parametrize("response", [{}, []])
def test_empty_or_malformed_market_data_response_is_rejected(response):
    client, api = make_client()
    api.getMarketData.return_value = response

    with pytest.raises(RuntimeError, match="empty market-data response"):
        client.get_market_data(
            mode="LTP",
            exchange_tokens={"NSE": ["99926000"]},
        )


def test_failed_api_response_is_rejected():

    client, api = make_client()

    api.getMarketData.return_value = {
        "status": False,
        "message": "Invalid request",
    }

    with pytest.raises(
        RuntimeError,
        match="Invalid request",
    ):
        client.get_market_data(
            mode="LTP",
            exchange_tokens={
                "NSE": [
                    "99926000"
                ]
            },
        )


def test_invalid_market_data_mode():

    client, _ = make_client()

    with pytest.raises(
        ValueError,
        match="mode must be one of",
    ):
        client.get_market_data(
            mode="INVALID",
            exchange_tokens={
                "NSE": [
                    "99926000"
                ]
            },
        )


def test_empty_exchange_tokens_rejected():

    client, _ = make_client()

    with pytest.raises(
        ValueError,
        match="exchange_tokens cannot be empty",
    ):
        client.get_market_data(
            mode="LTP",
            exchange_tokens={},
        )


def test_invalid_max_retries():

    with patch(
        "services.broker.angel_client.SmartConnect"
    ):

        with pytest.raises(
            ValueError,
            match="max_retries",
        ):
            AngelMarketDataClient(
                max_retries=0
            )


def test_negative_retry_delay():

    with patch(
        "services.broker.angel_client.SmartConnect"
    ):

        with pytest.raises(
            ValueError,
            match="retry_delay_seconds",
        ):
            AngelMarketDataClient(
                retry_delay_seconds=-1
            )


def test_invalid_backoff_multiplier():

    with patch(
        "services.broker.angel_client.SmartConnect"
    ):

        with pytest.raises(
            ValueError,
            match="retry_backoff_multiplier",
        ):
            AngelMarketDataClient(
                retry_backoff_multiplier=0.5
            )


@pytest.mark.parametrize(
    "response",
    (
        {
            "status": False,
            "message": "Too many requests",
            "errorcode": "AB1021",
            "data": None,
        },
        {
            "status": False,
            "message": (
                "Access denied because of "
                "exceeding rate limit"
            ),
            "errorcode": "",
            "data": None,
        },
        {
            "success": False,
            "message": "Forbidden",
            "errorCode": "AB1021",
            "data": None,
        },
        {
            "status": False,
            "message": "HTTP 403 Forbidden",
            "errorcode": "",
            "data": None,
        },
    ),
)
def test_documented_angel_rate_limit_responses_are_classified(
    response,
):
    assert (
        AngelMarketDataClient
        ._is_rate_limit_error(
            response=response,
        )
        is True
    )


def test_success_response_is_not_rate_limited_even_with_numeric_data():
    response = {
        "status": True,
        "message": "SUCCESS",
        "errorcode": "",
        "data": {
            "ltp": 24000.0,
            "http_code": 403,
        },
    }

    assert (
        AngelMarketDataClient
        ._is_rate_limit_error(
            response=response,
        )
        is False
    )


class _ForbiddenException(RuntimeError):
    status_code = 403


def test_http_403_exception_is_classified_as_rate_limit():
    exception = _ForbiddenException(
        "Access denied"
    )

    assert (
        AngelMarketDataClient
        ._is_rate_limit_error(
            exception=exception,
        )
        is True
    )


def test_unrelated_provider_failure_is_not_rate_limited():
    response = {
        "status": False,
        "message": "Symbol not found",
        "errorcode": "AB1009",
        "data": None,
    }

    assert (
        AngelMarketDataClient
        ._is_rate_limit_error(
            response=response,
        )
        is False
    )


@pytest.mark.parametrize(
    "response",
    (
        {
            "status": True,
            "message": "SUCCESS",
            "errorcode": "",
            "data": {},
        },
        {
            "status": "true",
            "message": "SUCCESS",
            "errorcode": "",
            "data": {},
        },
        {
            "success": True,
            "message": "SUCCESS",
            "errorCode": "",
            "data": {},
        },
        {
            "success": "success",
            "message": "SUCCESS",
            "errorCode": "",
            "data": {},
        },
    ),
)
def test_valid_angel_response_envelope_variants_are_accepted(
    response,
):
    assert (
        AngelMarketDataClient._validate_response(
            response,
            "market-data",
        )
        is response
    )


@pytest.mark.parametrize(
    "response",
    (
        {
            "status": False,
            "message": "Symbol not found",
            "errorcode": "AB1009",
            "data": None,
        },
        {
            "status": "false",
            "message": "Symbol not found",
            "errorcode": "AB1009",
            "data": None,
        },
        {
            "success": False,
            "message": "Symbol not found",
            "errorCode": "AB1009",
            "data": None,
        },
    ),
)
def test_failed_angel_response_envelope_variants_are_rejected(
    response,
):
    with pytest.raises(
        RuntimeError,
        match="AB1009",
    ):
        AngelMarketDataClient._validate_response(
            response,
            "market-data",
        )


@pytest.mark.parametrize(
    "response",
    (
        {
            "message": "SUCCESS",
            "data": {},
        },
        {
            "status": "unknown",
            "message": "SUCCESS",
            "data": {},
        },
        {
            "status": 1,
            "message": "SUCCESS",
            "data": {},
        },
    ),
)
def test_ambiguous_response_status_fails_closed(
    response,
):
    with pytest.raises(
        RuntimeError,
        match="invalid market-data response envelope",
    ):
        AngelMarketDataClient._validate_response(
            response,
            "market-data",
        )


@pytest.mark.parametrize(
    "response",
    (
        {
            "status": True,
            "message": "SUCCESS",
            "errorcode": "",
        },
        {
            "success": True,
            "message": "SUCCESS",
            "errorCode": "",
        },
    ),
)
def test_success_response_without_data_is_rejected(
    response,
):
    with pytest.raises(
        RuntimeError,
        match="without data",
    ):
        AngelMarketDataClient._validate_response(
            response,
            "market-data",
        )


@pytest.mark.parametrize(
    "error_code",
    (
        "AG8001",
        "AG8002",
        "AG8003",
        "AB8050",
        "AB8051",
        "AB1010",
        "AB1011",
    ),
)
def test_documented_authentication_codes_are_classified(
    error_code,
):
    response = {
        "status": False,
        "message": "Provider authentication failure",
        "errorcode": error_code,
        "data": None,
    }

    assert (
        AngelMarketDataClient
        ._is_authentication_error(
            response=response,
        )
        is True
    )


def test_error_code_camel_case_is_normalized():
    response = {
        "success": False,
        "message": "Token expired",
        "errorCode": "ag8002",
        "data": None,
    }

    assert (
        AngelMarketDataClient
        ._response_error_code(response)
        == "AG8002"
    )


def test_unrelated_error_code_is_not_authentication_failure():
    response = {
        "status": False,
        "message": "Symbol not found",
        "errorcode": "AB1009",
        "data": None,
    }

    assert (
        AngelMarketDataClient
        ._is_authentication_error(
            response=response,
        )
        is False
    )


@pytest.mark.parametrize(
    "data",
    (
        None,
        [],
        {},
        {
            "fetched": [],
        },
        {
            "unfetched": [],
        },
        {
            "fetched": {},
            "unfetched": [],
        },
        {
            "fetched": [],
            "unfetched": {},
        },
    ),
)
def test_market_data_payload_shape_is_validated(
    data,
):
    response = {
        "status": True,
        "message": "SUCCESS",
        "errorcode": "",
        "data": data,
    }

    with pytest.raises(RuntimeError):
        AngelMarketDataClient\
            ._validate_market_data_payload(
                response
            )


def test_market_data_payload_accepts_empty_result_lists():
    response = {
        "status": True,
        "message": "SUCCESS",
        "errorcode": "",
        "data": {
            "fetched": [],
            "unfetched": [],
        },
    }

    assert (
        AngelMarketDataClient
        ._validate_market_data_payload(
            response
        )
        is response
    )


@pytest.mark.parametrize(
    "data",
    (
        None,
        {},
        [],
        "invalid",
    ),
)
def test_historical_payload_requires_non_empty_list(
    data,
):
    response = {
        "status": True,
        "message": "SUCCESS",
        "errorcode": "",
        "data": data,
    }

    with pytest.raises(RuntimeError):
        AngelMarketDataClient\
            ._validate_historical_payload(
                response
            )


def test_historical_payload_accepts_candle_rows():
    response = {
        "status": True,
        "message": "SUCCESS",
        "errorcode": "",
        "data": [
            [
                "2026-08-06T10:00:00+05:30",
                24000,
                24010,
                23990,
                24005,
                0,
            ]
        ],
    }

    assert (
        AngelMarketDataClient
        ._validate_historical_payload(
            response
        )
        is response
    )


@pytest.mark.parametrize(
    "data",
    (
        None,
        {},
        "invalid",
        [None],
        [["not-a-dictionary"]],
    ),
)
def test_option_greeks_payload_requires_list_of_objects(
    data,
):
    response = {
        "status": True,
        "message": "SUCCESS",
        "errorcode": "",
        "data": data,
    }

    with pytest.raises(RuntimeError):
        AngelMarketDataClient\
            ._validate_option_greeks_payload(
                response
            )


def test_option_greeks_payload_accepts_empty_list():
    response = {
        "status": True,
        "message": "SUCCESS",
        "errorcode": "",
        "data": [],
    }

    assert (
        AngelMarketDataClient
        ._validate_option_greeks_payload(
            response
        )
        is response
    )


def test_get_ltp_matches_exact_exchange_and_token():
    client, api = make_client()

    api.getMarketData.return_value = {
        "status": True,
        "message": "SUCCESS",
        "errorcode": "",
        "data": {
            "fetched": [
                {
                    "exchange": "BSE",
                    "symbolToken": "99919000",
                    "tradingSymbol": "SENSEX",
                    "ltp": 81000.0,
                },
                {
                    "exchange": "NSE",
                    "symbolToken": "99926000",
                    "tradingSymbol": "NIFTY",
                    "ltp": 24500.0,
                },
            ],
            "unfetched": [],
        },
    }

    result = client.get_ltp(
        "NSE",
        "NIFTY",
        "99926000",
    )

    assert result["data"]["ltp"] == 24500.0
    assert result["data"]["exchange"] == "NSE"
    assert (
        result["data"]["symboltoken"]
        == "99926000"
    )


def test_get_ltp_rejects_missing_exact_identity():
    client, api = make_client()

    api.getMarketData.return_value = {
        "status": True,
        "message": "SUCCESS",
        "errorcode": "",
        "data": {
            "fetched": [
                {
                    "exchange": "BSE",
                    "symbolToken": "99919000",
                    "ltp": 81000.0,
                }
            ],
            "unfetched": [],
        },
    }

    with pytest.raises(
        RuntimeError,
        match="exactly one matching",
    ):
        client.get_ltp(
            "NSE",
            "NIFTY",
            "99926000",
        )


def test_get_ltp_rejects_matching_unfetched_error():
    client, api = make_client()

    api.getMarketData.return_value = {
        "status": True,
        "message": "SUCCESS",
        "errorcode": "",
        "data": {
            "fetched": [],
            "unfetched": [
                {
                    "exchange": "NSE",
                    "symbolToken": "99926000",
                    "message": "Symbol unavailable",
                    "errorCode": "AB4018",
                }
            ],
        },
    }

    with pytest.raises(
        RuntimeError,
        match="AB4018",
    ):
        client.get_ltp(
            "NSE",
            "NIFTY",
            "99926000",
        )


@pytest.mark.parametrize(
    "ltp",
    (
        None,
        "",
        "invalid",
        0,
        -1,
    ),
)
def test_get_ltp_rejects_invalid_price(
    ltp,
):
    client, api = make_client()

    api.getMarketData.return_value = {
        "status": True,
        "message": "SUCCESS",
        "errorcode": "",
        "data": {
            "fetched": [
                {
                    "exchange": "NSE",
                    "symbolToken": "99926000",
                    "ltp": ltp,
                }
            ],
            "unfetched": [],
        },
    }

    with pytest.raises(
        RuntimeError,
        match="LTP",
    ):
        client.get_ltp(
            "NSE",
            "NIFTY",
            "99926000",
        )


@pytest.mark.parametrize(
    "rows",
    (
        [
            [
                "2026-08-06T09:15:00",
                100,
                101,
                99,
                100,
                10,
            ]
        ],
        [
            [
                "2026-08-06T09:15:00+05:30",
                100,
                99,
                101,
                100,
                10,
            ]
        ],
        [
            [
                "2026-08-06T09:15:00+05:30",
                100,
                101,
                99,
                100,
                -1,
            ]
        ],
        [
            [
                "2026-08-06T09:15:00+05:30",
                100,
                101,
                99,
                100,
            ]
        ],
        [
            [
                "2026-08-06T09:20:00+05:30",
                100,
                101,
                99,
                100,
                10,
            ],
            [
                "2026-08-06T09:15:00+05:30",
                100,
                101,
                99,
                100,
                10,
            ],
        ],
    ),
)
def test_broker_historical_payload_rejects_invalid_candle_rows(
    rows,
):
    response = {
        "status": True,
        "message": "SUCCESS",
        "errorcode": "",
        "data": rows,
    }

    with pytest.raises(
        RuntimeError,
        match="invalid candle rows",
    ):
        AngelMarketDataClient\
            ._validate_historical_payload(
                response
            )


def test_broker_historical_payload_accepts_strict_valid_rows():
    response = {
        "status": True,
        "message": "SUCCESS",
        "errorcode": "",
        "data": [
            [
                "2026-08-06T09:15:00+05:30",
                100,
                101,
                99,
                100,
                10,
            ],
            [
                "2026-08-06T09:20:00+05:30",
                101,
                102,
                100,
                101,
                20,
            ],
        ],
    }

    assert (
        AngelMarketDataClient
        ._validate_historical_payload(
            response
        )
        is response
    )
