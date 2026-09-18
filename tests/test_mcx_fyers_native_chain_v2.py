"""Offline tests for native FYERS MCX option-chain path."""

from datetime import datetime, timezone

import pytest

from mcx.mcx_fyers_native_chain_v2 import (
    MCXFyersNativeChainError,
    MCXFyersNativeChainV2,
)


NOW = datetime(
    2026,
    9,
    18,
    10,
    0,
    tzinfo=timezone.utc,
)


class FakeIdentity:
    def resolve_active(
        self,
        product,
        **kwargs,
    ):
        strikes = {
            "CRUDEOILM": (
                9450.0,
                9500.0,
                9550.0,
            ),
            "GOLDM": (
                124900.0,
                125000.0,
                125100.0,
            ),
            "SILVERM": (
                179000.0,
                180000.0,
                181000.0,
            ),
        }[product]

        calls = {}
        puts = {}

        for strike in strikes:
            for option_type, target in (
                ("CE", calls),
                ("PE", puts),
            ):
                symbol = (
                    f"MCX:{product}_"
                    f"{int(strike)}_"
                    f"{option_type}"
                )

                target[strike] = {
                    "symbol": symbol,
                    "token": symbol,
                    "provider": "FYERS",
                    "provider_symbol": (
                        symbol
                    ),
                }

        future_symbol = (
            f"MCX:{product}_FUT"
        )

        return {
            "status": "OK",
            "provider": "FYERS",
            "futures": {
                "symbol": future_symbol,
                "token": future_symbol,
                "expiry": "2026-09-30",
            },
            "option_expiry": (
                "2026-09-25"
            ),
            "calls": calls,
            "puts": puts,
        }


class FakeData:
    provider = "FYERS"

    def __init__(self, product):
        self.product = product

    def ltpData(
        self,
        exchange,
        tradingsymbol,
        symboltoken,
    ):
        prices = {
            "CRUDEOILM": 9500.0,
            "GOLDM": 125000.0,
            "SILVERM": 180000.0,
        }

        return {
            "status": True,
            "provider": "FYERS",
            "data": {
                "ltp": prices[
                    self.product
                ],
            },
        }


class FakeClient:
    def __init__(self, product):
        self.product = product
        self.optionchain_calls = 0
        self.depth_calls = 0

    def optionchain(self, data):
        self.optionchain_calls += 1

        strikes = {
            "CRUDEOILM": (
                9450.0,
                9500.0,
                9550.0,
            ),
            "GOLDM": (
                124900.0,
                125000.0,
                125100.0,
            ),
            "SILVERM": (
                179000.0,
                180000.0,
                181000.0,
            ),
        }[self.product]

        rows = []

        for strike in strikes:
            for option_type in (
                "CE",
                "PE",
            ):
                rows.append({
                    "symbol": (
                        f"MCX:{self.product}_"
                        f"{int(strike)}_"
                        f"{option_type}"
                    ),
                    "strike_price": strike,
                    "option_type": option_type,
                    "ltp": 100.0,
                    "oi": (
                        1000
                        if option_type == "CE"
                        else 1200
                    ),
                    "volume": 500,
                    "bid": 99.5,
                    "ask": 100.5,
                    "fyToken": (
                        f"{self.product}-"
                        f"{option_type}-"
                        f"{int(strike)}"
                    ),
                    "expiry": (
                        "2026-09-25"
                    ),
                })

        return {
            "s": "ok",
            "data": {
                "expiryData": [
                    {
                        "date": "25-09-2026",
                        "expiry": 1790274600,
                    }
                ],
                "optionsChain": rows
            },
        }

    def depth(self, data):
        self.depth_calls += 1
        raise AssertionError(
            "native chain must not "
            "request per-option depth"
        )


@pytest.mark.parametrize(
    "product",
    (
        "CRUDEOILM",
        "GOLDM",
        "SILVERM",
    ),
)
def test_native_chain_uses_one_optionchain_and_zero_depth_fanout(product):
    client = FakeClient(product)

    engine = MCXFyersNativeChainV2(
        data_client=client,
        identity=FakeIdentity(),
        data_api=FakeData(product),
        clock=lambda: NOW,
    )

    result = engine.build(
        product,
        window_steps=20,
        as_of=NOW,
    )

    assert result["status"] == "OK"
    assert result["provider"] == "FYERS"

    assert (
        result[
            "option_chain_request_count"
        ]
        == 1
    )

    assert (
        result[
            "per_contract_depth_requests"
        ]
        == 0
    )

    assert client.optionchain_calls == 1
    assert client.depth_calls == 0

    assert result["ce_data"]
    assert result["pe_data"]

    assert result["pcr_oi"] == 1.2
    assert result["max_pain"] is not None


def test_silverm_atm_and_identity_are_preserved():
    client = FakeClient(
        "SILVERM"
    )

    result = (
        MCXFyersNativeChainV2(
            data_client=client,
            identity=FakeIdentity(),
            data_api=FakeData(
                "SILVERM"
            ),
            clock=lambda: NOW,
        )
        .build(
            "SILVERM",
            as_of=NOW,
        )
    )

    assert result["atm"] == 180000.0

    option = result[
        "ce_data"
    ][180000.0]

    assert option[
        "provider_symbol"
    ] == (
        "MCX:SILVERM_180000_CE"
    )

    assert option[
        "token"
    ] == (
        "MCX:SILVERM_180000_CE"
    )


def test_unknown_product_fails_closed():
    engine = MCXFyersNativeChainV2(
        data_client=FakeClient(
            "CRUDEOILM"
        ),
        identity=FakeIdentity(),
        data_api=FakeData(
            "CRUDEOILM"
        ),
        clock=lambda: NOW,
    )

    with pytest.raises(
        MCXFyersNativeChainError
    ):
        engine.build(
            "NATGASMINI"
        )


def test_module_has_no_angel_or_order_authority():
    import pathlib

    path = pathlib.Path(
        "src/mcx/"
        "mcx_fyers_native_chain_v2.py"
    )

    text = path.read_text(
        encoding="utf-8"
    )

    forbidden = (
        "SmartConnect",
        "ANGEL_API_KEY",
        "ANGEL_USER_ID",
        "ANGEL_PASSWORD",
        "ANGEL_TOTP_SECRET",
        "placeOrder",
        "place_order",
        "FyersOrderSocket",
    )

    assert not [
        marker
        for marker in forbidden
        if marker in text
    ]
