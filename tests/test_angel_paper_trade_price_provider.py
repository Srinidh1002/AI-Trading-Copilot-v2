import pytest

from services.angel_paper_trade_price_provider import (
    AngelPaperTradePriceProvider,
)


class FakeMarketDataClient:

    def __init__(
        self,
        response=None,
        error=None,
    ):
        self.response = response
        self.error = error
        self.calls = []

    def get_market_data(
        self,
        mode,
        exchange_tokens,
    ):
        self.calls.append(
            {
                "mode": mode,
                "exchange_tokens": exchange_tokens,
            }
        )

        if self.error is not None:
            raise self.error

        return self.response


def valid_response(
    ltp=125.50,
):
    return {
        "data": {
            "fetched": [
                {
                    "ltp": ltp
                }
            ]
        }
    }


def make_trade(
    symboltoken="12345",
    metadata=None,
):
    return {
        "trade_id": "paper-1",
        "status": "OPEN",
        "underlying": "NIFTY",
        "exchange": "NSE",
        "option_symbol": "NIFTY26JUL25000CE",
        "symboltoken": symboltoken,
        "metadata": (
            {}
            if metadata is None
            else metadata
        ),
    }


def test_requires_client():

    with pytest.raises(
        ValueError
    ):
        AngelPaperTradePriceProvider(
            None
        )


def test_client_requires_market_data_method():

    with pytest.raises(
        ValueError
    ):
        AngelPaperTradePriceProvider(
            object()
        )


@pytest.mark.parametrize(
    "exchange",
    [
        None,
        "",
        "   ",
        123,
    ],
)
def test_invalid_default_exchange_rejected(
    exchange,
):

    client = (
        FakeMarketDataClient()
    )

    with pytest.raises(
        ValueError
    ):
        AngelPaperTradePriceProvider(
            client,
            default_option_exchange=exchange,
        )


def test_fetches_ltp():

    client = (
        FakeMarketDataClient(
            valid_response(
                125.50
            )
        )
    )

    provider = (
        AngelPaperTradePriceProvider(
            client
        )
    )

    price = provider(
        make_trade()
    )

    assert price == 125.50


def test_uses_ltp_mode():

    client = (
        FakeMarketDataClient(
            valid_response()
        )
    )

    provider = (
        AngelPaperTradePriceProvider(
            client
        )
    )

    provider(
        make_trade()
    )

    assert (
        client.calls[0][
            "mode"
        ]
        == "LTP"
    )


def test_defaults_option_exchange_to_nfo():

    client = (
        FakeMarketDataClient(
            valid_response()
        )
    )

    provider = (
        AngelPaperTradePriceProvider(
            client
        )
    )

    provider(
        make_trade()
    )

    assert (
        client.calls[0][
            "exchange_tokens"
        ]
        == {
            "NFO": [
                "12345"
            ]
        }
    )


def test_does_not_use_underlying_nse_exchange():

    client = (
        FakeMarketDataClient(
            valid_response()
        )
    )

    provider = (
        AngelPaperTradePriceProvider(
            client
        )
    )

    provider(
        make_trade()
    )

    assert (
        "NSE"
        not in client.calls[0][
            "exchange_tokens"
        ]
    )


def test_uses_market_data_exchange_metadata():

    client = (
        FakeMarketDataClient(
            valid_response()
        )
    )

    provider = (
        AngelPaperTradePriceProvider(
            client
        )
    )

    provider(
        make_trade(
            metadata={
                "market_data_exchange": "BFO"
            }
        )
    )

    assert (
        client.calls[0][
            "exchange_tokens"
        ]
        == {
            "BFO": [
                "12345"
            ]
        }
    )


def test_uses_option_exchange_metadata():

    client = (
        FakeMarketDataClient(
            valid_response()
        )
    )

    provider = (
        AngelPaperTradePriceProvider(
            client
        )
    )

    provider(
        make_trade(
            metadata={
                "option_exchange": "NFO"
            }
        )
    )

    assert (
        client.calls[0][
            "exchange_tokens"
        ]
        == {
            "NFO": [
                "12345"
            ]
        }
    )


def test_market_data_exchange_has_priority():

    client = (
        FakeMarketDataClient(
            valid_response()
        )
    )

    provider = (
        AngelPaperTradePriceProvider(
            client
        )
    )

    provider(
        make_trade(
            metadata={
                "market_data_exchange": "BFO",
                "option_exchange": "NFO",
            }
        )
    )

    assert (
        client.calls[0][
            "exchange_tokens"
        ]
        == {
            "BFO": [
                "12345"
            ]
        }
    )


def test_custom_default_exchange():

    client = (
        FakeMarketDataClient(
            valid_response()
        )
    )

    provider = (
        AngelPaperTradePriceProvider(
            client,
            default_option_exchange="bfo",
        )
    )

    provider(
        make_trade()
    )

    assert (
        client.calls[0][
            "exchange_tokens"
        ]
        == {
            "BFO": [
                "12345"
            ]
        }
    )


@pytest.mark.parametrize(
    "trade",
    [
        None,
        "invalid",
        [],
        123,
    ],
)
def test_invalid_trade_rejected(
    trade,
):

    client = (
        FakeMarketDataClient(
            valid_response()
        )
    )

    provider = (
        AngelPaperTradePriceProvider(
            client
        )
    )

    with pytest.raises(
        ValueError
    ):
        provider(
            trade
        )


@pytest.mark.parametrize(
    "token",
    [
        None,
        "",
        "   ",
    ],
)
def test_missing_symboltoken_rejected(
    token,
):

    client = (
        FakeMarketDataClient(
            valid_response()
        )
    )

    provider = (
        AngelPaperTradePriceProvider(
            client
        )
    )

    with pytest.raises(
        ValueError
    ):
        provider(
            make_trade(
                symboltoken=token
            )
        )


def test_numeric_symboltoken_converted_to_string():

    client = (
        FakeMarketDataClient(
            valid_response()
        )
    )

    provider = (
        AngelPaperTradePriceProvider(
            client
        )
    )

    provider(
        make_trade(
            symboltoken=12345
        )
    )

    assert (
        client.calls[0][
            "exchange_tokens"
        ]
        == {
            "NFO": [
                "12345"
            ]
        }
    )


def test_invalid_metadata_rejected():

    client = (
        FakeMarketDataClient(
            valid_response()
        )
    )

    provider = (
        AngelPaperTradePriceProvider(
            client
        )
    )

    with pytest.raises(
        ValueError
    ):
        provider(
            make_trade(
                metadata="invalid"
            )
        )


@pytest.mark.parametrize(
    "response",
    [
        None,
        [],
        {},
        {
            "data": None
        },
        {
            "data": {}
        },
        {
            "data": {
                "fetched": None
            }
        },
        {
            "data": {
                "fetched": []
            }
        },
        {
            "data": {
                "fetched": [
                    "invalid"
                ]
            }
        },
        {
            "data": {
                "fetched": [
                    {}
                ]
            }
        },
    ],
)
def test_invalid_broker_response_rejected(
    response,
):

    client = (
        FakeMarketDataClient(
            response
        )
    )

    provider = (
        AngelPaperTradePriceProvider(
            client
        )
    )

    with pytest.raises(
        ValueError
    ):
        provider(
            make_trade()
        )


@pytest.mark.parametrize(
    "ltp",
    [
        None,
        "",
        "abc",
        0,
        -1,
        True,
        False,
        float(
            "nan"
        ),
        float(
            "inf"
        ),
        float(
            "-inf"
        ),
    ],
)
def test_invalid_ltp_rejected(
    ltp,
):

    client = (
        FakeMarketDataClient(
            valid_response(
                ltp
            )
        )
    )

    provider = (
        AngelPaperTradePriceProvider(
            client
        )
    )

    with pytest.raises(
        ValueError
    ):
        provider(
            make_trade()
        )


def test_numeric_string_ltp_accepted():

    client = (
        FakeMarketDataClient(
            valid_response(
                "125.75"
            )
        )
    )

    provider = (
        AngelPaperTradePriceProvider(
            client
        )
    )

    assert (
        provider(
            make_trade()
        )
        == 125.75
    )


def test_broker_exception_propagates():

    client = (
        FakeMarketDataClient(
            error=RuntimeError(
                "Broker unavailable"
            )
        )
    )

    provider = (
        AngelPaperTradePriceProvider(
            client
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Broker unavailable",
    ):
        provider(
            make_trade()
        )


def test_get_price_method():

    client = (
        FakeMarketDataClient(
            valid_response(
                150
            )
        )
    )

    provider = (
        AngelPaperTradePriceProvider(
            client
        )
    )

    assert (
        provider.get_price(
            make_trade()
        )
        == 150.0
    )