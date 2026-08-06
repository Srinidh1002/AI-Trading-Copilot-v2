from unittest.mock import MagicMock

import pytest

from services.broker.two_market_quote_service import (
    CANONICAL_EXCHANGE_TOKENS,
    CanonicalTwoMarketFullQuotes,
    fetch_canonical_two_market_full_quotes,
)


def _quote(
    *,
    exchange,
    token,
    symbol,
    ltp,
):
    return {
        "exchange": exchange,
        "symbolToken": token,
        "tradingSymbol": symbol,
        "ltp": ltp,
        "open": 24490.0,
        "high": 24520.0,
        "low": 24480.0,
        "close": 24495.0,
    }


def _response(
    *,
    fetched,
    unfetched=None,
):
    return {
        "status": True,
        "message": "SUCCESS",
        "errorcode": "",
        "data": {
            "fetched": fetched,
            "unfetched": (
                []
                if unfetched is None
                else unfetched
            ),
        },
    }


def _client(response):
    client = MagicMock()
    client.get_market_data.return_value = (
        response
    )
    return client


def test_fetches_both_indices_in_exactly_one_full_request():
    client = _client(
        _response(
            fetched=[
                _quote(
                    exchange="NSE",
                    token="99926000",
                    symbol="NIFTY",
                    ltp=24500,
                ),
                _quote(
                    exchange="BSE",
                    token="99919000",
                    symbol="SENSEX",
                    ltp=80500,
                ),
            ]
        )
    )

    result = (
        fetch_canonical_two_market_full_quotes(
            client
        )
    )

    assert isinstance(
        result,
        CanonicalTwoMarketFullQuotes,
    )

    client.get_market_data.assert_called_once_with(
        "FULL",
        CANONICAL_EXCHANGE_TOKENS,
    )


def test_result_order_is_nifty_then_sensex_even_when_provider_reverses():
    client = _client(
        _response(
            fetched=[
                _quote(
                    exchange="BSE",
                    token="99919000",
                    symbol="SENSEX",
                    ltp=80500,
                ),
                _quote(
                    exchange="NSE",
                    token="99926000",
                    symbol="NIFTY",
                    ltp=24500,
                ),
            ]
        )
    )

    result = (
        fetch_canonical_two_market_full_quotes(
            client
        )
    )

    assert tuple(
        item.market
        for item in result.ordered()
    ) == (
        "NIFTY",
        "SENSEX",
    )

    assert result.nifty.ltp == 24500.0
    assert result.sensex.ltp == 80500.0


def test_result_exposes_exact_canonical_identities():
    client = _client(
        _response(
            fetched=[
                _quote(
                    exchange="NSE",
                    token="99926000",
                    symbol="NIFTY",
                    ltp=24500,
                ),
                _quote(
                    exchange="BSE",
                    token="99919000",
                    symbol="SENSEX",
                    ltp=80500,
                ),
            ]
        )
    )

    result = (
        fetch_canonical_two_market_full_quotes(
            client
        )
    )

    assert (
        result.nifty.market,
        result.nifty.exchange,
        result.nifty.symboltoken,
    ) == (
        "NIFTY",
        "NSE",
        "99926000",
    )

    assert (
        result.sensex.market,
        result.sensex.exchange,
        result.sensex.symboltoken,
    ) == (
        "SENSEX",
        "BSE",
        "99919000",
    )


@pytest.mark.parametrize(
    "fetched",
    (
        [],
        [
            _quote(
                exchange="NSE",
                token="99926000",
                symbol="NIFTY",
                ltp=24500,
            )
        ],
    ),
)
def test_missing_canonical_quote_fails_closed(
    fetched,
):
    client = _client(
        _response(
            fetched=fetched,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="exactly one",
    ):
        fetch_canonical_two_market_full_quotes(
            client
        )


def test_duplicate_canonical_quote_fails_closed():
    nifty = _quote(
        exchange="NSE",
        token="99926000",
        symbol="NIFTY",
        ltp=24500,
    )

    client = _client(
        _response(
            fetched=[
                nifty,
                dict(nifty),
                _quote(
                    exchange="BSE",
                    token="99919000",
                    symbol="SENSEX",
                    ltp=80500,
                ),
            ]
        )
    )

    with pytest.raises(
        RuntimeError,
        match="exactly one NIFTY",
    ):
        fetch_canonical_two_market_full_quotes(
            client
        )


def test_unexpected_fetched_identity_fails_closed():
    client = _client(
        _response(
            fetched=[
                _quote(
                    exchange="NSE",
                    token="99926000",
                    symbol="NIFTY",
                    ltp=24500,
                ),
                _quote(
                    exchange="BSE",
                    token="99919000",
                    symbol="SENSEX",
                    ltp=80500,
                ),
                _quote(
                    exchange="NSE",
                    token="99926017",
                    symbol="BANKNIFTY",
                    ltp=55000,
                ),
            ]
        )
    )

    with pytest.raises(
        RuntimeError,
        match="unexpected fetched identity",
    ):
        fetch_canonical_two_market_full_quotes(
            client
        )


@pytest.mark.parametrize(
    (
        "exchange",
        "token",
        "market",
    ),
    (
        (
            "NSE",
            "99926000",
            "NIFTY",
        ),
        (
            "BSE",
            "99919000",
            "SENSEX",
        ),
    ),
)
def test_canonical_unfetched_record_fails_closed(
    exchange,
    token,
    market,
):
    client = _client(
        _response(
            fetched=[],
            unfetched=[
                {
                    "exchange": exchange,
                    "symbolToken": token,
                    "errorCode": "AB4018",
                    "message": "Symbol unavailable",
                }
            ],
        )
    )

    with pytest.raises(
        RuntimeError,
        match=rf"{market} FULL quote was unfetched.*AB4018",
    ):
        fetch_canonical_two_market_full_quotes(
            client
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
def test_invalid_ltp_fails_closed(
    ltp,
):
    client = _client(
        _response(
            fetched=[
                _quote(
                    exchange="NSE",
                    token="99926000",
                    symbol="NIFTY",
                    ltp=ltp,
                ),
                _quote(
                    exchange="BSE",
                    token="99919000",
                    symbol="SENSEX",
                    ltp=80500,
                ),
            ]
        )
    )

    with pytest.raises(
        RuntimeError,
        match="NIFTY FULL quote",
    ):
        fetch_canonical_two_market_full_quotes(
            client
        )


@pytest.mark.parametrize(
    "response",
    (
        None,
        [],
        {},
        {
            "status": True,
            "data": None,
        },
        {
            "status": True,
            "data": {
                "fetched": None,
                "unfetched": [],
            },
        },
        {
            "status": True,
            "data": {
                "fetched": [],
                "unfetched": None,
            },
        },
    ),
)
def test_malformed_response_fails_closed(
    response,
):
    client = _client(response)

    with pytest.raises(RuntimeError):
        fetch_canonical_two_market_full_quotes(
            client
        )


def test_service_does_not_expose_order_submission_methods():
    client = _client(
        _response(
            fetched=[
                _quote(
                    exchange="NSE",
                    token="99926000",
                    symbol="NIFTY",
                    ltp=24500,
                ),
                _quote(
                    exchange="BSE",
                    token="99919000",
                    symbol="SENSEX",
                    ltp=80500,
                ),
            ]
        )
    )

    fetch_canonical_two_market_full_quotes(
        client
    )

    assert (
        client.method_calls
        == [
            (
                "get_market_data",
                (
                    "FULL",
                    CANONICAL_EXCHANGE_TOKENS,
                ),
                {},
            )
        ]
    )


def test_shared_helper_uses_repository_shared_client(
    monkeypatch,
):
    client = _client(
        _response(
            fetched=[
                _quote(
                    exchange="NSE",
                    token="99926000",
                    symbol="NIFTY",
                    ltp=24500,
                ),
                _quote(
                    exchange="BSE",
                    token="99919000",
                    symbol="SENSEX",
                    ltp=80500,
                ),
            ]
        )
    )

    monkeypatch.setattr(
        "services.broker.shared_client.get_market_client",
        lambda: client,
    )

    from services.broker.two_market_quote_service import (
        fetch_shared_canonical_two_market_full_quotes,
    )

    result = (
        fetch_shared_canonical_two_market_full_quotes()
    )

    assert result.nifty.ltp == 24500.0
    assert result.sensex.ltp == 80500.0

    client.get_market_data.assert_called_once_with(
        "FULL",
        CANONICAL_EXCHANGE_TOKENS,
    )
