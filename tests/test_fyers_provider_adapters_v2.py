from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.broker.fyers_provider_adapters_v2 import (
    FyersHistoricalDataProviderV2,
    FyersProviderAdapterError,
    FyersQuoteDepthProviderV2,
    FyersRequestControllerV2,
    FyersStreamingUnavailableV2,
    InjectedFyersInstrumentResolverV2,
)
from services.contracts.provider_runtime_bundle_v2 import (
    ProviderRuntimeBundleV2,
)


class FakeClient:
    def __init__(self):
        self.history_calls = []
        self.quote_calls = []
        self.depth_calls = []

    def history(self, data):
        self.history_calls.append(data)

        return {
            "s": "ok",
            "candles": [
                [
                    1790000000,
                    100,
                    105,
                    99,
                    103,
                    1000,
                    50000,
                ]
            ],
        }

    def quotes(self, data):
        self.quote_calls.append(data)

        symbol = data["symbols"]

        return {
            "s": "ok",
            "d": [
                {
                    "n": symbol,
                    "v": {
                        "symbol": symbol,
                        "lp": 103.5,
                        "bid": 103.4,
                        "ask": 103.6,
                        "volume": 1000,
                        "fyToken": "FY1",
                        "tt": 1790000000,
                    },
                }
            ],
        }

    def depth(self, data):
        self.depth_calls.append(data)

        symbol = data["symbol"]

        return {
            "s": "ok",
            "d": {
                symbol: {
                    "ltp": 103.5,
                    "bids": [
                        {
                            "price": 103.4
                        }
                    ],
                    "ask": [
                        {
                            "price": 103.6
                        }
                    ],
                    "oi": 50000,
                    "v": 1000,
                    "o": 100,
                    "h": 105,
                    "l": 99,
                    "c": 103,
                }
            },
        }


INSTRUMENT = {
    "provider_symbol":
        "NSE:NIFTY26SEPFUT"
}


def test_historical_adapter():
    client = FakeClient()

    adapter = FyersHistoricalDataProviderV2(
        client
    )

    rows = adapter.get_candles(
        INSTRUMENT,
        interval="FIVE_MINUTE",
        start=datetime(
            2026,
            9,
            17,
            9,
            15,
            tzinfo=timezone.utc,
        ),
        end=datetime(
            2026,
            9,
            17,
            10,
            15,
            tzinfo=timezone.utc,
        ),
    )

    assert len(rows) == 1
    assert rows[0]["close"] == 103
    assert (
        rows[0]["open_interest"]
        == 50000
    )

    assert (
        client.history_calls[0][
            "resolution"
        ]
        == "5"
    )


def test_quote_adapter():
    client = FakeClient()

    adapter = FyersQuoteDepthProviderV2(
        client
    )

    quote = adapter.get_quote(
        INSTRUMENT
    )

    assert (
        quote["provider"]
        == "FYERS"
    )

    assert (
        quote["last_price"]
        == 103.5
    )

    assert (
        quote[
            "live_execution_eligible"
        ]
        is False
    )


def test_depth_adapter():
    client = FakeClient()

    adapter = FyersQuoteDepthProviderV2(
        client
    )

    depth = adapter.get_depth(
        INSTRUMENT
    )

    assert (
        depth["open_interest"]
        == 50000
    )

    assert (
        depth["bids"][0]["price"]
        == 103.4
    )

    assert (
        depth["asks"][0]["price"]
        == 103.6
    )


def test_request_controller_contract():
    controller = (
        FyersRequestControllerV2()
    )

    assert (
        controller.wait_for_slot(
            "QUOTE",
            1,
        )
        == 0.0
    )

    assert (
        controller.record_rate_limit(
            "QUOTE",
            1,
            2,
        )
        == 0.0
    )

    assert (
        controller.record_success(
            "QUOTE"
        )
        is None
    )


def test_injected_resolver():
    adapter = (
        InjectedFyersInstrumentResolverV2(
            lambda **kwargs: {
                "provider_symbol":
                    "NSE:NIFTY50-INDEX",
                "market_symbol":
                    kwargs[
                        "market_symbol"
                    ],
            }
        )
    )

    result = adapter.resolve(
        market_symbol="NIFTY",
        instrument_type="UNDERLYING",
    )

    assert (
        result["provider_symbol"]
        == "NSE:NIFTY50-INDEX"
    )


def test_injected_resolver_fails_closed():
    adapter = (
        InjectedFyersInstrumentResolverV2(
            lambda **kwargs: {}
        )
    )

    with pytest.raises(
        FyersProviderAdapterError
    ):
        adapter.resolve(
            market_symbol="NIFTY",
            instrument_type="UNDERLYING",
        )


def test_streaming_placeholder_fails_closed():
    streaming = (
        FyersStreamingUnavailableV2()
    )

    with pytest.raises(
        FyersProviderAdapterError
    ):
        streaming.subscribe(
            (
                INSTRUMENT,
            ),
            lambda item: None,
        )


def test_runtime_bundle_structural_contract():
    client = FakeClient()

    resolver = (
        InjectedFyersInstrumentResolverV2(
            lambda **kwargs: {
                "provider_symbol":
                    "NSE:NIFTY50-INDEX"
            }
        )
    )

    bundle = ProviderRuntimeBundleV2(
        provider="FYERS",
        resolver=resolver,
        historical=FyersHistoricalDataProviderV2(
            client
        ),
        quote_depth=FyersQuoteDepthProviderV2(
            client
        ),
        streaming=FyersStreamingUnavailableV2(),
        request_controller=FyersRequestControllerV2(),
    )

    assert bundle.provider == "FYERS"
    assert bundle.data_only is True
    assert (
        bundle.order_capability_allowed
        is False
    )
    assert (
        bundle.automatic_fallback_allowed
        is False
    )


def test_no_order_methods():
    client = FakeClient()

    objects = (
        FyersHistoricalDataProviderV2(
            client
        ),
        FyersQuoteDepthProviderV2(
            client
        ),
        FyersRequestControllerV2(),
        FyersStreamingUnavailableV2(),
    )

    forbidden = (
        "placeOrder",
        "place_order",
        "modifyOrder",
        "cancelOrder",
        "orderBook",
    )

    for obj in objects:
        assert not any(
            hasattr(
                obj,
                name,
            )
            for name in forbidden
        )
