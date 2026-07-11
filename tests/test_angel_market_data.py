from unittest.mock import MagicMock, patch

from services.broker.angel_client import AngelMarketDataClient


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
            "jwtToken": "fake_jwt_token"
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
        "data": {},
    }

    mock_api.getMarketData.return_value = {
        "status": True,
        "message": "SUCCESS",
        "data": {
            "fetched": []
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