from __future__ import annotations

import pytest

from services.broker.fyers_response_normalizer_v2 import (
    FyersResponseNormalizationError,
)
from services.options.fyers_option_chain_provider_v2 import (
    FyersOptionChainProviderV2,
)


class FakeClient:
    def __init__(self):
        self.calls = []

    def optionchain(
        self,
        data=None,
    ):
        self.calls.append(
            data
        )

        return {
            "s": "ok",
            "data": {
                "optionsChain": [
                    {
                        "symbol":
                            "NSE:NIFTY2692223300CE",
                        "strike_price":
                            23300,
                        "option_type":
                            "CE",
                        "ltp":
                            160,
                        "oi":
                            1000,
                        "oich":
                            100,
                        "volume":
                            5000,
                        "bid":
                            159.9,
                        "ask":
                            160.1,
                        "fyToken":
                            "CE1",
                        "greeks": {
                            "delta": 0.55,
                            "gamma": 0.001,
                            "theta": -12.5,
                            "vega": 8.2,
                            "iv": 13.7,
                        },
                    },
                    {
                        "symbol":
                            "NSE:NIFTY2692223300PE",
                        "strike_price":
                            23300,
                        "option_type":
                            "PE",
                        "ltp":
                            95,
                        "oi":
                            2000,
                        "oich":
                            200,
                        "volume":
                            6000,
                        "bid":
                            94.9,
                        "ask":
                            95.1,
                        "fyToken":
                            "PE1",
                        "greeks": {
                            "delta": -0.45,
                            "gamma": 0.0011,
                            "theta": -11.5,
                            "vega": 8.0,
                            "iv": 14.1,
                        },
                    },
                ]
            },
        }


def test_native_option_chain_uses_one_provider_call():
    client = FakeClient()

    provider = (
        FyersOptionChainProviderV2(
            client
        )
    )

    result = provider.get_option_chain(
        underlying_symbol=
            "NSE:NIFTY50-INDEX",
        strike_count=5,
    )

    assert len(
        client.calls
    ) == 1

    assert (
        result["request_count"]
        == 1
    )

    assert (
        result[
            "per_contract_depth_requests"
        ]
        == 0
    )


def test_native_option_chain_preserves_ce_pe_data():
    client = FakeClient()

    provider = (
        FyersOptionChainProviderV2(
            client
        )
    )

    result = provider.get_option_chain(
        underlying_symbol=
            "NSE:NIFTY50-INDEX",
        strike_count=5,
    )

    rows = result[
        "rows"
    ]

    assert len(rows) == 2
    assert rows[0]["type"] == "CE"
    assert rows[1]["type"] == "PE"
    assert rows[0]["oi"] == 1000
    assert rows[1]["bid"] == 94.9


def test_option_chain_passes_requested_expiry():
    client = FakeClient()

    provider = (
        FyersOptionChainProviderV2(
            client
        )
    )

    provider.get_option_chain(
        underlying_symbol=
            "NSE:NIFTY50-INDEX",
        strike_count=7,
        expiry_timestamp=123456789,
    )

    assert (
        client.calls[0][
            "timestamp"
        ]
        == 123456789
    )


def test_option_chain_fails_closed_on_provider_error():
    class BadClient:
        def optionchain(
            self,
            data=None,
        ):
            return {
                "s": "error"
            }

    provider = (
        FyersOptionChainProviderV2(
            BadClient()
        )
    )

    with pytest.raises(
        FyersResponseNormalizationError
    ):
        provider.get_option_chain(
            underlying_symbol=
                "NSE:NIFTY50-INDEX",
            strike_count=5,
        )

def test_option_chain_requests_and_preserves_provider_greeks_and_iv():
    client = FakeClient()
    provider = FyersOptionChainProviderV2(client)

    result = provider.get_option_chain(
        underlying_symbol="NSE:NIFTY50-INDEX",
        strike_count=5,
    )

    assert client.calls[0]["greeks"] == 1
    ce, pe = result["rows"]
    assert ce["delta"] == 0.55
    assert ce["gamma"] == 0.001
    assert ce["theta"] == -12.5
    assert ce["vega"] == 8.2
    assert ce["iv"] == 13.7
    assert pe["delta"] == -0.45
    assert pe["iv"] == 14.1
