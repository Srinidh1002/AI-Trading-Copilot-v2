from __future__ import annotations

import ast
from pathlib import Path

import pytest

from services.broker.fyers_data_compatibility_v2 import (
    FyersDataOnlyCompatibilityV2,
)
from services.broker.fyers_response_normalizer_v2 import (
    FyersResponseNormalizationError,
)


class FakeFyersClient:
    def __init__(self) -> None:
        self.quote_requests = []
        self.history_requests = []
        self.depth_requests = []

    def quotes(self, data=None):
        self.quote_requests.append(
            data
        )

        symbol = data["symbols"]

        return {
            "s": "ok",
            "code": 200,
            "d": [
                {
                    "n": symbol,
                    "v": {
                        "symbol":
                            symbol,
                        "lp":
                            23398.1,
                        "bid":
                            23398.0,
                        "ask":
                            23398.5,
                        "volume":
                            1234,
                        "tt":
                            1790000000,
                        "fyToken":
                            "FY-1",
                    },
                }
            ],
        }

    def history(self, data=None):
        self.history_requests.append(
            data
        )

        return {
            "s": "ok",
            "candles": [
                [
                    1790000000,
                    100.0,
                    105.0,
                    99.0,
                    103.0,
                    1000,
                ]
            ],
        }

    def depth(self, data=None):
        self.depth_requests.append(
            data
        )

        symbol = data["symbol"]

        return {
            "s": "ok",
            "d": {
                symbol: {
                    "ltp":
                        101.5,
                    "oi":
                        50000,
                    "v":
                        12500,
                    "o":
                        100.0,
                    "h":
                        103.0,
                    "l":
                        99.0,
                    "c":
                        100.5,
                    "bids": [
                        {
                            "price":
                                101.4,
                            "volume":
                                10,
                            "ord":
                                1,
                        }
                    ],
                    "ask": [
                        {
                            "price":
                                101.6,
                            "volume":
                                20,
                            "ord":
                                2,
                        }
                    ],
                }
            },
        }


def resolver(
    exchange: str,
    tradingsymbol: str | None,
    symboltoken: str,
) -> str:
    mapping = {
        "26000":
            "NSE:NIFTY50-INDEX",

        "101":
            "NSE:NIFTY2692223300CE",

        "102":
            "NSE:NIFTY2692223300PE",
    }

    return mapping[
        symboltoken
    ]


def build():
    client = FakeFyersClient()

    adapter = (
        FyersDataOnlyCompatibilityV2(
            client=client,
            symbol_resolver=resolver,
        )
    )

    return client, adapter


def test_ltp_data_uses_quotes_and_returns_angel_shape():
    client, adapter = build()

    result = adapter.ltpData(
        "NSE",
        "NIFTY 50",
        "26000",
    )

    assert (
        client.quote_requests
        == [
            {
                "symbols":
                    "NSE:NIFTY50-INDEX"
            }
        ]
    )

    assert result[
        "status"
    ] is True

    assert result[
        "data"
    ][
        "ltp"
    ] == 23398.1

    assert result[
        "data"
    ][
        "symboltoken"
    ] == "26000"


def test_candle_data_translates_interval_and_time_range():
    client, adapter = build()

    result = adapter.getCandleData(
        {
            "exchange":
                "NSE",

            "symboltoken":
                "26000",

            "interval":
                "FIVE_MINUTE",

            "fromdate":
                "2026-09-17 09:15",

            "todate":
                "2026-09-17 15:30",
        }
    )

    assert result[
        "status"
    ] is True

    assert len(
        result[
            "data"
        ]
    ) == 1

    request = client.history_requests[
        0
    ]

    assert request[
        "symbol"
    ] == "NSE:NIFTY50-INDEX"

    assert request[
        "resolution"
    ] == "5"

    assert request[
        "date_format"
    ] == "0"

    assert isinstance(
        request[
            "range_from"
        ],
        int,
    )

    assert (
        request[
            "range_to"
        ]
        >
        request[
            "range_from"
        ]
    )


def test_full_market_data_uses_depth_and_compatibility_aliases():
    client, adapter = build()

    result = adapter.getMarketData(
        "FULL",
        {
            "NFO": [
                "101"
            ]
        },
    )

    assert client.depth_requests == [
        {
            "symbol":
                "NSE:NIFTY2692223300CE",
            "ohlcv_flag":
                "1",
        }
    ]

    row = result[
        "data"
    ][
        "fetched"
    ][0]

    assert row[
        "symbolToken"
    ] == "101"

    assert row[
        "ltp"
    ] == 101.5

    assert row[
        "opnInterest"
    ] == 50000

    assert row[
        "tradeVolume"
    ] == 12500

    assert row[
        "bid"
    ] == 101.4

    assert row[
        "ask"
    ] == 101.6

    assert row[
        "bestFiveBuyData"
    ][0][
        "price"
    ] == 101.4

    assert row[
        "bestFiveSellData"
    ][0][
        "price"
    ] == 101.6


def test_full_market_data_supports_multiple_tokens():
    client, adapter = build()

    result = adapter.getMarketData(
        "FULL",
        {
            "NFO": [
                "101",
                "102",
            ]
        },
    )

    assert len(
        result[
            "data"
        ][
            "fetched"
        ]
    ) == 2

    assert len(
        client.depth_requests
    ) == 2


def test_non_full_market_data_fails_closed():
    _, adapter = build()

    with pytest.raises(
        FyersResponseNormalizationError
    ):
        adapter.getMarketData(
            "LTP",
            {
                "NFO": [
                    "101"
                ]
            },
        )


def test_adapter_exposes_no_auth_or_order_methods():
    _, adapter = build()

    forbidden = (
        "generateSession",
        "getfeedToken",
        "placeOrder",
        "place_order",
        "modifyOrder",
        "cancelOrder",
        "orderBook",
    )

    assert not any(
        hasattr(
            adapter,
            name,
        )
        for name in forbidden
    )

    assert adapter.data_only is True
    assert (
        adapter.order_capability_allowed
        is False
    )
    assert (
        adapter.automatic_fallback_allowed
        is False
    )


def test_adapter_module_has_no_provider_sdk_or_network_imports():
    path = Path(
        "services/broker/fyers_data_compatibility_v2.py"
    )

    tree = ast.parse(
        path.read_text(
            encoding="utf-8"
        )
    )

    imports = []

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Import,
        ):
            imports.extend(
                alias.name
                for alias in node.names
            )

        elif (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module
        ):
            imports.append(
                node.module
            )

    forbidden = (
        "fyers_apiv3",
        "SmartApi",
        "requests",
        "urllib",
        "socket",
        "httpx",
        "aiohttp",
        "websocket",
        "websockets",
    )

    assert not any(
        name.startswith(
            forbidden
        )
        for name in imports
    )
