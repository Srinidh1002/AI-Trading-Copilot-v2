from datetime import datetime, timedelta, timezone

import pytest

from services.angel_paper_trade_price_provider import (
    AngelPaperTradePriceProvider,
)


NOW = datetime(
    2026,
    8,
    10,
    9,
    30,
    0,
    tzinfo=timezone.utc,
)


class FakeClient:
    def __init__(self, response):
        self.response = response
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
        return self.response


def _trade():
    return {
        "trade_id": "paper-1",
        "status": "OPEN",
        "underlying": "NIFTY",
        "exchange": "NSE",
        "option_symbol": "NIFTY26AUG25000CE",
        "symboltoken": "12345",
        "metadata": {
            "option_exchange": "NFO",
        },
    }


def _response(timestamp):
    record = {
        "ltp": 125.50,
    }

    if timestamp is not None:
        record[
            "exchFeedTime"
        ] = timestamp

    return {
        "data": {
            "fetched": [
                record
            ]
        }
    }


def _provider(timestamp):
    return AngelPaperTradePriceProvider(
        FakeClient(
            _response(timestamp)
        ),
        clock=lambda: NOW,
    )


def test_full_quote_with_fresh_provider_timestamp_is_accepted():
    provider = _provider(
        (
            NOW
            - timedelta(
                milliseconds=500
            )
        ).isoformat()
    )

    assert provider(_trade()) == 125.50

    assert (
        provider.market_data_client
        .calls[0]["mode"]
        == "FULL"
    )


def test_quote_older_than_lifecycle_one_second_is_rejected():
    provider = _provider(
        (
            NOW
            - timedelta(
                seconds=1.001
            )
        ).isoformat()
    )

    with pytest.raises(
        ValueError,
        match="stale",
    ):
        provider(_trade())


def test_missing_provider_timestamp_is_rejected():
    provider = _provider(None)

    with pytest.raises(
        ValueError,
        match="provider timestamp is missing",
    ):
        provider(_trade())


def test_malformed_provider_timestamp_is_rejected():
    provider = _provider("not-a-timestamp")

    with pytest.raises(
        ValueError,
        match="provider timestamp is invalid",
    ):
        provider(_trade())


def test_excessive_future_provider_timestamp_is_rejected():
    provider = _provider(
        (
            NOW
            + timedelta(
                seconds=5.001
            )
        ).isoformat()
    )

    with pytest.raises(
        ValueError,
        match="future skew",
    ):
        provider(_trade())


def test_allowed_future_skew_is_accepted():
    provider = _provider(
        (
            NOW
            + timedelta(
                seconds=5
            )
        ).isoformat()
    )

    assert provider(_trade()) == 125.50


def test_custom_quote_age_ceiling_is_supported():
    provider = AngelPaperTradePriceProvider(
        FakeClient(
            _response(
                (
                    NOW
                    - timedelta(
                        seconds=2
                    )
                ).isoformat()
            )
        ),
        maximum_quote_age_seconds=3,
        clock=lambda: NOW,
    )

    assert provider(_trade()) == 125.50


@pytest.mark.parametrize(
    "value",
    (
        -1,
        True,
        float("inf"),
        float("nan"),
    ),
)
def test_invalid_quote_age_configuration_is_rejected(
    value,
):
    with pytest.raises(ValueError):
        AngelPaperTradePriceProvider(
            FakeClient(
                _response(
                    NOW.isoformat()
                )
            ),
            maximum_quote_age_seconds=value,
        )
