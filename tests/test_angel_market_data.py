from unittest.mock import MagicMock, patch
from datetime import date

import pytest

import services.broker.angel_client as angel_client_module
from services.broker.angel_client import AngelMarketDataClient


@pytest.fixture(autouse=True)
def _hermetic_angel_credentials(monkeypatch):
    """Keep Angel unit tests independent of the developer's real .env."""
    monkeypatch.setattr(
        angel_client_module,
        "ANGEL_API_KEY",
        "TEST_ONLY_API_KEY",
    )
    monkeypatch.setattr(
        angel_client_module,
        "ANGEL_CLIENT_ID",
        "TEST_ONLY_CLIENT_ID",
    )
    monkeypatch.setattr(
        angel_client_module,
        "ANGEL_PIN",
        "0000",
    )
    monkeypatch.setattr(
        angel_client_module,
        "ANGEL_TOTP_SECRET",
        "JBSWY3DPEHPK3PXP",
    )


@patch("services.broker.angel_client.pyotp.TOTP")
@patch("services.broker.angel_client.SmartConnect")
def test_angel_login(
    mock_smart_connect,
    mock_totp,
):
    mock_api = MagicMock()
    mock_smart_connect.return_value = mock_api

    mock_totp.return_value.now.return_value = "123456"

    mock_api.generateSession.return_value = {
        "status": True,
        "message": "SUCCESS",
        "data": {
            "jwtToken": "fake_jwt_token",
            "refreshToken": "fake_refresh_token",
            "feedToken": "fake_feed_token",
        },
    }

    client = AngelMarketDataClient()

    result = client.login()

    assert result["status"] is True
    assert client.authenticated is True

    mock_api.generateSession.assert_called_once()


@patch("services.broker.angel_client.pyotp.TOTP")
@patch("services.broker.angel_client.SmartConnect")
def test_get_market_data(
    mock_smart_connect,
    mock_totp,
):
    mock_api = MagicMock()
    mock_smart_connect.return_value = mock_api

    mock_totp.return_value.now.return_value = "123456"

    mock_api.generateSession.return_value = {
        "status": True,
        "message": "SUCCESS",
        "data": {
            "jwtToken": "fake_jwt_token",
            "refreshToken": "fake_refresh_token",
            "feedToken": "fake_feed_token",
        },
    }

    mock_api.getMarketData.return_value = {
        "status": True,
        "message": "SUCCESS",
        "data": {
            "fetched": [],
            "unfetched": [],
        },
    }

    client = AngelMarketDataClient()

    result = client.get_market_data(
        mode="FULL",
        exchange_tokens={
            "NSE": ["99926000"]
        },
    )

    assert result["status"] is True

    mock_api.getMarketData.assert_called_once_with(
        "FULL",
        {
            "NSE": ["99926000"]
        },
    )


@patch("services.broker.angel_client.SmartConnect")
def test_invalid_market_data_mode(
    mock_smart_connect,
):
    client = AngelMarketDataClient()

    try:
        client.get_market_data(
            mode="INVALID",
            exchange_tokens={
                "NSE": ["99926000"]
            },
        )

        assert False

    except ValueError as error:
        assert "LTP, OHLC, FULL" in str(error)

@patch("services.broker.angel_client.pyotp.TOTP")
@patch("services.broker.angel_client.SmartConnect")
def test_login_accepts_normalized_success_envelope(
    mock_smart_connect,
    mock_totp,
):
    mock_api = MagicMock()
    mock_smart_connect.return_value = mock_api
    mock_totp.return_value.now.return_value = "123456"

    mock_api.generateSession.return_value = {
        "status": "true",
        "message": "SUCCESS",
        "errorcode": "",
        "data": {
            "jwtToken": "jwt",
            "refreshToken": "refresh",
            "feedToken": "feed",
        },
    }

    client = AngelMarketDataClient()
    result = client.login()

    assert result["status"] == "true"
    assert client.authenticated is True
    assert client.session is result


@pytest.mark.parametrize(
    "data",
    (
        None,
        {},
        {
            "jwtToken": "jwt",
            "refreshToken": "refresh",
        },
        {
            "jwtToken": "",
            "refreshToken": "refresh",
            "feedToken": "feed",
        },
        {
            "jwtToken": "jwt",
            "refreshToken": None,
            "feedToken": "feed",
        },
    ),
)
@patch("services.broker.angel_client.pyotp.TOTP")
@patch("services.broker.angel_client.SmartConnect")
def test_login_rejects_incomplete_session_tokens(
    mock_smart_connect,
    mock_totp,
    data,
):
    mock_api = MagicMock()
    mock_smart_connect.return_value = mock_api
    mock_totp.return_value.now.return_value = "123456"

    mock_api.generateSession.return_value = {
        "status": True,
        "message": "SUCCESS",
        "errorcode": "",
        "data": data,
    }

    client = AngelMarketDataClient()

    with pytest.raises(
        RuntimeError,
        match=(
            "invalid session data|"
            "incomplete authentication data|"
            "successful login response without usable data"
        ),
    ):
        client.login()

    assert client.authenticated is False
    assert client.session is None


@patch("services.broker.angel_client.pyotp.TOTP")
@patch("services.broker.angel_client.SmartConnect")
def test_failed_login_never_preserves_previous_session(
    mock_smart_connect,
    mock_totp,
):
    mock_api = MagicMock()
    mock_smart_connect.return_value = mock_api
    mock_totp.return_value.now.return_value = "123456"

    mock_api.generateSession.return_value = {
        "status": False,
        "message": "Token expired",
        "errorcode": "AG8002",
        "data": None,
    }

    client = AngelMarketDataClient()
    client.authenticated = True
    client.session = {
        "status": True,
        "data": {
            "jwtToken": "old",
            "refreshToken": "old",
            "feedToken": "old",
        },
    }

    with pytest.raises(
        RuntimeError,
        match="AG8002",
    ):
        client.login(force=True)

    assert client.authenticated is False
    assert client.session is None


@patch("services.broker.angel_client.pyotp.TOTP")
@patch("services.broker.angel_client.SmartConnect")
def test_same_day_session_is_reused_without_another_login(
    mock_smart_connect,
    mock_totp,
):
    api = MagicMock()
    mock_smart_connect.return_value = api
    mock_totp.return_value.now.return_value = "123456"
    api.generateSession.return_value = {
        "status": True,
        "data": {"jwtToken": "jwt", "refreshToken": "refresh", "feedToken": "feed"},
    }
    client = AngelMarketDataClient(current_date=lambda: date(2026, 8, 10))

    client.login()
    client.login()

    api.generateSession.assert_called_once()


@patch("services.broker.angel_client.pyotp.TOTP")
@patch("services.broker.angel_client.SmartConnect")
def test_prior_day_session_is_discarded_before_authenticated_request(
    mock_smart_connect,
    mock_totp,
):
    api = MagicMock()
    mock_smart_connect.return_value = api
    mock_totp.return_value.now.return_value = "123456"
    api.generateSession.return_value = {
        "status": True,
        "data": {"jwtToken": "jwt", "refreshToken": "refresh", "feedToken": "feed"},
    }
    api.getMarketData.return_value = {
        "status": True,
        "data": {"fetched": [], "unfetched": []},
    }
    current_day = [date(2026, 8, 10)]
    client = AngelMarketDataClient(current_date=lambda: current_day[0])

    client.login()
    current_day[0] = date(2026, 8, 11)
    client.get_market_data("FULL", {"NSE": ["99926000"]})

    assert api.generateSession.call_count == 2
    assert api.generateToken.call_count == 0
    api.getMarketData.assert_called_once()
