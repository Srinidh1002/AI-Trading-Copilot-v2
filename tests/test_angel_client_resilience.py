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
            ]
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