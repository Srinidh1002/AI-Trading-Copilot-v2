"""Offline tests for the MCX FYERS data/identity bridge.

No credentials.
No network.
No broker orders.
No PAPER state.
No certification mutation.
"""

from datetime import datetime, timezone

import pytest

from services.broker.fyers_symbol_master_v2 import (
    FyersSymbolMasterIndexV2,
)
from mcx.mcx_fyers_bridge_v2 import (
    MCXFyersBridgeError,
    SUPPORTED_MCX_FYERS_PRODUCTS,
    build_mcx_fyers_bridge_v2,
)


NOW = datetime(
    2026,
    9,
    18,
    10,
    0,
    tzinfo=timezone.utc,
)


def _rows():
    rows = []

    specs = {
        "CRUDEOILM": {
            "strike": 9500.0,
            "lot": 10,
            "future_tick": 0.05,
            "option_tick": 0.05,
        },
        "GOLDM": {
            "strike": 125000.0,
            "lot": 100,
            "future_tick": 1.0,
            "option_tick": 0.50,
        },
        "SILVERM": {
            "strike": 180000.0,
            "lot": 5,
            "future_tick": 1.0,
            "option_tick": 0.50,
        },
    }

    for product, cfg in specs.items():

        # Same-day future must NOT become active.
        rows.append({
            "symbol": f"MCX:{product}26SEP18FUT",
            "exch": "MCX",
            "segment": "MCX_COM",
            "instrument_type": "FUT",
            "underlying_symbol": product,
            "expiry": "2026-09-18",
            "fyToken": f"{product}-F-SAME",
            "lot_size": cfg["lot"],
            "tick_size": cfg["future_tick"],
        })

        rows.append({
            "symbol": f"MCX:{product}26SEP30FUT",
            "exch": "MCX",
            "segment": "MCX_COM",
            "instrument_type": "FUT",
            "underlying_symbol": product,
            "expiry": "2026-09-30",
            "fyToken": f"{product}-F-NEXT",
            "lot_size": cfg["lot"],
            "tick_size": cfg["future_tick"],
        })

        # Same-day CE/PE must be excluded by MCX expiry safety.
        for option_type in ("CE", "PE"):
            rows.append({
                "symbol": (
                    f"MCX:{product}26SEP18"
                    f"{int(cfg['strike'])}{option_type}"
                ),
                "exch": "MCX",
                "segment": "MCX_COM",
                "instrument_type": "OPT",
                "underlying_symbol": product,
                "expiry": "2026-09-18",
                "strike": cfg["strike"],
                "option_type": option_type,
                "fyToken": (
                    f"{product}-{option_type}-SAME"
                ),
                "lot_size": cfg["lot"],
                "tick_size": cfg["option_tick"],
            })

        # Nearest eligible option expiry.
        for offset in (-1, 0, 1):
            strike = (
                cfg["strike"]
                + offset
                * (
                    50
                    if product == "CRUDEOILM"
                    else (
                        100
                        if product == "GOLDM"
                        else 1000
                    )
                )
            )

            for option_type in ("CE", "PE"):
                rows.append({
                    "symbol": (
                        f"MCX:{product}26SEP25"
                        f"{int(strike)}{option_type}"
                    ),
                    "exch": "MCX",
                    "segment": "MCX_COM",
                    "instrument_type": "OPT",
                    "underlying_symbol": product,
                    "expiry": "2026-09-25",
                    "strike": strike,
                    "option_type": option_type,
                    "fyToken": (
                        f"{product}-{option_type}-"
                        f"{int(strike)}"
                    ),
                    "lot_size": cfg["lot"],
                    "tick_size": cfg["option_tick"],
                })

    return rows


class FakeStore:
    def __init__(self):
        self.index = (
            FyersSymbolMasterIndexV2
            .from_rows(
                _rows(),
                "MCX_COM",
            )
        )

    def get_index(self, segment):
        if segment != "MCX_COM":
            raise RuntimeError(
                f"unexpected segment: {segment}"
            )
        return self.index


class EmptyStore:
    def get_index(self, segment):
        raise RuntimeError(
            f"missing {segment}"
        )


class FakeClient:
    def quotes(self, data):
        symbol = data["symbols"]

        return {
            "s": "ok",
            "d": [{
                "n": symbol,
                "v": {
                    "symbol": symbol,
                    "lp": 100.0,
                    "bid": 99.5,
                    "ask": 100.5,
                    "volume": 1000,
                    "fyToken": "LIVE-TOKEN",
                    "tt": 1789725600,
                },
            }],
        }

    def depth(self, data):
        symbol = data["symbol"]

        return {
            "s": "ok",
            "d": {
                symbol: {
                    "ltp": 100.0,
                    "bids": [
                        {
                            "price": 99.5,
                            "volume": 20,
                            "ord": 2,
                        }
                    ],
                    "ask": [
                        {
                            "price": 100.5,
                            "volume": 25,
                            "ord": 3,
                        }
                    ],
                    "oi": 12345,
                    "volume": 4567,
                    "o": 98.0,
                    "h": 102.0,
                    "l": 97.0,
                    "c": 99.0,
                }
            },
        }

    def history(self, data):
        # Deliberately include seventh OI field. The MCX compatibility
        # bridge must protect legacy six-column pandas readers.
        return {
            "s": "ok",
            "candles": [
                [
                    1789725600,
                    98.0,
                    101.0,
                    97.0,
                    100.0,
                    10000,
                    54321,
                ],
                [
                    1789725900,
                    100.0,
                    102.0,
                    99.0,
                    101.0,
                    12000,
                    55000,
                ],
            ],
        }


def _bridge(store=None):
    return build_mcx_fyers_bridge_v2(
        data_client=FakeClient(),
        master_store=(
            store
            if store is not None
            else FakeStore()
        ),
        clock=lambda: NOW,
    )


def test_supported_products_are_exact_requested_mcx_three():
    assert SUPPORTED_MCX_FYERS_PRODUCTS == (
        "CRUDEOILM",
        "GOLDM",
        "SILVERM",
    )


@pytest.mark.parametrize(
    "product",
    (
        "CRUDEOILM",
        "GOLDM",
        "SILVERM",
    ),
)
def test_identity_resolves_future_and_nearest_non_same_day_options(product):
    bridge = _bridge()

    result = bridge.identity.resolve_active(
        product,
        as_of=NOW,
    )

    assert result["status"] == "OK"
    assert result["provider"] == "FYERS"

    assert (
        result["futures"]["expiry"]
        == "2026-09-30"
    )

    assert (
        result["option_expiry"]
        == "2026-09-25"
    )

    assert result["calls"]
    assert result["puts"]

    assert all(
        item["provider"] == "FYERS"
        for item
        in result["calls"].values()
    )

    assert all(
        item["expiry"] != "2026-09-18"
        for item
        in (
            list(result["calls"].values())
            + list(result["puts"].values())
        )
    )


def test_silverm_legacy_chain_shape_preserves_real_strike_after_division():
    result = (
        _bridge()
        .identity
        .resolve_active(
            "SILVERM",
            as_of=NOW,
        )
    )

    assert 180000.0 in result["calls"]

    legacy_record = (
        result["calls"][180000.0]
    )

    # Existing mcx_chain divides record strike by 100.
    assert (
        legacy_record["strike"] / 100.0
        == 180000.0
    )

    assert legacy_record["token"].startswith(
        "MCX:SILVERM"
    )


def test_full_market_data_uses_fyers_depth_and_keeps_legacy_shape():
    bridge = _bridge()

    identity = bridge.identity.resolve_active(
        "SILVERM",
        as_of=NOW,
    )

    option = identity["calls"][180000.0]

    result = bridge.data.getMarketData(
        "FULL",
        {
            "MCX": [
                option["token"]
            ]
        },
    )

    row = result["data"]["fetched"][0]

    assert row["symbolToken"] == option["token"]
    assert row["ltp"] == 100.0

    assert row["provider"] == "FYERS"
    assert row["data_only"] is True
    assert (
        row["live_execution_eligible"]
        is False
    )

    assert row["opnInterest"] == 12345
    assert row["tradeVolume"] == 4567

    assert (
        row["bestFiveBuyData"][0]["price"]
        == 99.5
    )

    assert (
        row["bestFiveSellData"][0]["price"]
        == 100.5
    )

    assert (
        row["bestFiveBuyData"][0][
            "quantity"
        ]
        == 20
    )


def test_candles_are_fyers_backed_and_six_column_legacy_safe():
    bridge = _bridge()

    identity = bridge.identity.resolve_active(
        "CRUDEOILM",
        as_of=NOW,
    )

    future = identity["futures"]

    result = bridge.data.getCandleData({
        "exchange": "MCX",
        "symboltoken": future["token"],
        "interval": "FIVE_MINUTE",
        "fromdate": "2026-09-18 09:00",
        "todate": "2026-09-18 10:00",
    })

    assert result["provider"] == "FYERS"
    assert result["data_only"] is True

    assert len(result["data"]) == 2
    assert all(
        len(row) == 6
        for row in result["data"]
    )

    assert result["data"][0][4] == 100.0
    assert result["data"][0][5] == 10000


def test_provider_symbol_resolution_fails_closed_outside_mcx():
    bridge = _bridge()

    identity = bridge.identity.resolve_active(
        "GOLDM",
        as_of=NOW,
    )

    token = next(
        iter(identity["calls"].values())
    )["token"]

    with pytest.raises(
        MCXFyersBridgeError
    ):
        bridge.identity.resolve_provider_symbol(
            "NSE",
            None,
            token,
        )


def test_missing_master_evidence_returns_unavailable_not_fallback():
    bridge = _bridge(
        store=EmptyStore()
    )

    result = bridge.identity.resolve_active(
        "SILVERM",
        as_of=NOW,
    )

    assert (
        result["status"]
        == "EVIDENCE_UNAVAILABLE_IDENTITY"
    )

    assert result["futures"] is None
    assert result["calls"] == {}
    assert result["puts"] == {}


def test_natgasmini_is_not_supported_by_new_bridge():
    bridge = _bridge()

    with pytest.raises(
        MCXFyersBridgeError
    ):
        bridge.identity.resolve_active(
            "NATGASMINI",
            as_of=NOW,
        )


def test_bridge_has_no_order_or_fallback_capability():
    bridge = _bridge()

    assert bridge.provider == "FYERS"
    assert bridge.data_only is True
    assert (
        bridge.order_capability_allowed
        is False
    )
    assert (
        bridge.automatic_fallback_allowed
        is False
    )
    assert (
        bridge.live_execution_eligible
        is False
    )

    assert bridge.data.provider == "FYERS"
    assert bridge.data.data_only is True
    assert (
        bridge.data.order_capability_allowed
        is False
    )
    assert (
        bridge.data.automatic_fallback_allowed
        is False
    )

    forbidden = (
        "place_order",
        "placeOrder",
        "modify_order",
        "modifyOrder",
        "cancel_order",
        "cancelOrder",
    )

    assert not [
        name
        for name in forbidden
        if hasattr(bridge.data, name)
    ]


def test_crudeoilm_full_depth_preserves_provider_quantity_until_semantics_proven():
    bridge = _bridge()

    identity = bridge.identity.resolve_active(
        "CRUDEOILM",
        as_of=NOW,
    )

    calls = identity["calls"]

    assert calls

    option = next(iter(calls.values()))

    result = bridge.data.getMarketData(
        "FULL",
        {"MCX": [option["token"]]},
    )

    row = result["data"]["fetched"][0]

    # Preserve provider depth exactly as received.
    assert row["bestFiveBuyData"][0]["quantity"] == 20

    assert row["bestFiveSellData"][0]["quantity"] == 25

    assert row["depth"]["buy"][0]["quantity"] == 20

    assert row["depth"]["sell"][0]["quantity"] == 25

    assert row["provider_depth_quantity_unit"] == "UNVERIFIED"

    assert row["depth_quantity_semantics_verified"] is False

    assert "provider_quantity_lots" not in row["bestFiveBuyData"][0]

    assert "provider_quantity_lots" not in row["bestFiveSellData"][0]

    assert "depth_quantity_scale" not in row

    # Non-depth traded volume remains untouched.
    assert row["tradeVolume"] == 4567


def test_silverm_full_depth_is_not_scaled_before_live_quantity_proof():
    bridge = _bridge()

    identity = bridge.identity.resolve_active(
        "SILVERM",
        as_of=NOW,
    )

    option = next(iter(identity["calls"].values()))

    result = bridge.data.getMarketData(
        "FULL",
        {"MCX": [option["token"]]},
    )

    row = result["data"]["fetched"][0]

    # SILVERM has not yet completed its live FYERS quantity calibration.
    assert row["bestFiveBuyData"][0]["quantity"] == 20

    assert "provider_quantity_lots" not in row["bestFiveBuyData"][0]

    assert "depth_quantity_scale" not in row
