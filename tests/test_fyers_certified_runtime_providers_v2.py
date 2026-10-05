from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.paper_orchestration.fyers_certified_runtime_providers_v2 import (
    FyersCertifiedIndexOptionPipelineV2,
    FyersCertifiedProviderCompositionError,
    build_fyers_certified_runtime_providers_v2,
)


NOW = datetime(2026, 10, 5, 5, 0, 2, tzinfo=timezone.utc)
QUOTE_TS = int(datetime(2026, 10, 5, 5, 0, 0, tzinfo=timezone.utc).timestamp())


class Resolver:
    def resolve(self, **kwargs):
        market = kwargs["market_symbol"]
        kind = kwargs["instrument_type"]
        if kind == "UNDERLYING":
            return {
                "provider_symbol": (
                    "NSE:NIFTY50-INDEX"
                    if market == "NIFTY"
                    else "BSE:SENSEX-INDEX"
                )
            }
        strike = int(float(kwargs["strike"]))
        option_type = kwargs["option_type"]
        prefix = "NSE:NIFTY" if market == "NIFTY" else "BSE:SENSEX"
        return {
            "provider_symbol": f"{prefix}26O06{strike}{option_type}",
            "provider_token": f"{market}-{strike}-{option_type}",
            "lot_size": 65 if market == "NIFTY" else 20,
            "tick_size": 0.05,
            "metadata_status": "VERIFIED",
        }


class Client:
    def __init__(self):
        self.quote_calls = []

    def quotes(self, data=None):
        self.quote_calls.append(data)
        symbol = data["symbols"]
        price = 22460.0 if "NIFTY" in symbol else 72000.0
        return {
            "s": "ok",
            "d": [
                {
                    "n": symbol,
                    "v": {
                        "symbol": symbol,
                        "lp": price,
                        "tt": QUOTE_TS,
                        "fyToken": "X",
                    },
                }
            ],
        }

    def history(self, data=None):
        return {"s": "ok", "candles": []}

    def depth(self, data=None):
        symbol = data["symbol"]
        return {
            "s": "ok",
            "d": {
                symbol: {
                    "ltp": 100.0,
                    "bids": [{"price": 99.5, "volume": 10}],
                    "ask": [{"price": 100.5, "volume": 10}],
                }
            },
        }

    def optionchain(self, data=None):
        return {
            "s": "ok",
            "data": {
                "expiryData": [],
                "optionsChain": [],
            },
        }


def instrument_rows():
    return [
        {
            "exch_seg": "NSE",
            "token": "99926000",
            "symbol": "NIFTY 50",
            "name": "NIFTY 50",
            "instrumenttype": "AMXIDX",
        },
        {
            "exch_seg": "BSE",
            "token": "99919000",
            "symbol": "SENSEX",
            "name": "SENSEX",
            "instrumenttype": "AMXIDX",
        },
    ]


def build(clock=lambda: NOW):
    client = Client()
    bundle = build_fyers_certified_runtime_providers_v2(
        data_client=client,
        resolver=Resolver(),
        instrument_rows=instrument_rows(),
        clock=clock,
        cache_enabled=False,
        maximum_quote_age_seconds=10.0,
    )
    return client, bundle


def test_fyers_certified_bundle_uses_data_only_components():
    _, bundle = build()

    assert callable(bundle.quote_reader)
    assert callable(bundle.analysis_pipeline.analyse)
    assert isinstance(
        bundle.option_decision_pipeline,
        FyersCertifiedIndexOptionPipelineV2,
    )
    assert bundle.option_decision_pipeline.data_only is True
    assert bundle.option_decision_pipeline.order_capability_allowed is False
    assert (
        bundle.option_decision_pipeline.automatic_fallback_allowed
        is False
    )


def test_fyers_certified_quote_reader_preserves_fyers_timestamp_authority():
    client, bundle = build()

    quote = bundle.quote_reader(
        "NSE",
        "99926000",
        "NIFTY",
    )

    assert client.quote_calls == [
        {"symbols": "NSE:NIFTY50-INDEX"}
    ]
    assert quote["provider"] == "FYERS"
    assert quote["spot_price"] == 22460.0
    assert quote["timestamp_source"] == "FYERS_PROVIDER_EXCHANGE_TIMESTAMP"
    assert quote["market_timestamp"].timestamp() == QUOTE_TS
    assert quote["received_at"] == NOW
    assert quote["quote_age_seconds"] == 2.0


def test_fyers_certified_quote_reader_fails_closed_on_stale_quote():
    _, bundle = build(
        clock=lambda: datetime(
            2026, 10, 5, 5, 2, 0,
            tzinfo=timezone.utc,
        )
    )

    with pytest.raises(
        FyersCertifiedProviderCompositionError,
        match="STALE",
    ):
        bundle.quote_reader(
            "NSE",
            "99926000",
            "NIFTY",
        )


def test_fyers_certified_option_pipeline_refuses_legacy_analyse():
    _, bundle = build()

    with pytest.raises(
        RuntimeError,
        match="FYERS_CERTIFIED_CAPTURE_ONLY",
    ):
        bundle.option_decision_pipeline.analyse()
