from datetime import datetime, timezone

import pytest

from services.broker.fyers_legacy_identity_resolver_v2 import (
    FyersLegacyIdentityResolutionError,
    FyersLegacyIdentityResolverV2,
)


NOW = datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc)


class FakeResolver:
    def __init__(self):
        self.calls = []

    def resolve(self, **kwargs):
        self.calls.append(kwargs)
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
        if kind == "OPTION":
            return {"provider_symbol": f"FYERS:{market}:{kwargs['strike']}:{kwargs['option_type']}"}
        raise AssertionError(kwargs)


def rows():
    return [
        {
            "exch_seg": "NSE",
            "token": "99926000",
            "symbol": "NIFTY",
            "name": "NIFTY 50",
            "instrumenttype": "AMXIDX",
        },
        {
            "exch_seg": "BSE",
            "token": "1",
            "symbol": "SENSEX",
            "name": "SENSEX",
            "instrumenttype": "AMXIDX",
        },
        {
            "exch_seg": "NSE",
            "token": "2885",
            "symbol": "RELIANCE-EQ",
            "name": "RELIANCE",
            "instrumenttype": "AMXEQTY",
        },
        {
            "exch_seg": "NSE",
            "token": "99926017",
            "symbol": "INDIA VIX",
            "name": "INDIA VIX",
            "instrumenttype": "AMXIDX",
        },
        {
            "exch_seg": "NFO",
            "token": "12345",
            "symbol": "NIFTY17SEP2625000CE",
            "expiry": "17SEP2026",
            "strike": "2500000",
            "instrumenttype": "OPTIDX",
        },
        {
            "exch_seg": "BFO",
            "token": "67890",
            "symbol": "SENSEX24SEP2676800PE",
            "expiry": "24SEP2026",
            "strike": "7680000",
            "instrumenttype": "OPTIDX",
        },
    ]


def build():
    resolver = FakeResolver()
    translator = FyersLegacyIdentityResolverV2(
        instrument_rows=rows(),
        resolver=resolver,
        clock=lambda: NOW,
    )
    return resolver, translator


def test_nifty_index_maps_through_production_resolver():
    resolver, translator = build()
    assert translator("NSE", "NIFTY", "99926000") == "NSE:NIFTY50-INDEX"
    assert resolver.calls[-1]["instrument_type"] == "UNDERLYING"
    assert resolver.calls[-1]["market_symbol"] == "NIFTY"


def test_sensex_index_maps_through_production_resolver():
    resolver, translator = build()
    assert translator("BSE", "SENSEX", "1") == "BSE:SENSEX-INDEX"
    assert resolver.calls[-1]["market_symbol"] == "SENSEX"


def test_sensex_legacy_candle_token_maps_without_trading_symbol():
    resolver, translator = build()
    assert translator("BSE", None, "1") == "BSE:SENSEX-INDEX"
    assert resolver.calls[-1]["market_symbol"] == "SENSEX"


def test_nse_equity_maps_without_network_or_fallback():
    _, translator = build()
    assert translator("NSE", "RELIANCE-EQ", "2885") == "NSE:RELIANCE-EQ"
    assert translator.data_only is True
    assert translator.order_capability_allowed is False
    assert translator.automatic_fallback_allowed is False


def test_india_vix_maps_to_fyers_index_symbol():
    _, translator = build()
    assert translator("NSE", "INDIA VIX", "99926017") == "NSE:INDIAVIX-INDEX"


def test_nifty_option_uses_expiry_strike_and_type():
    resolver, translator = build()
    assert translator("NFO", "NIFTY17SEP2625000CE", "12345") == "FYERS:NIFTY:25000.0:CE"
    call = resolver.calls[-1]
    assert call["instrument_type"] == "OPTION"
    assert call["strike"] == 25000.0
    assert call["option_type"] == "CE"
    assert call["expiry"].isoformat() == "2026-09-17"


def test_sensex_option_uses_production_resolver():
    resolver, translator = build()
    assert translator("BFO", "SENSEX24SEP2676800PE", "67890") == "FYERS:SENSEX:76800.0:PE"
    call = resolver.calls[-1]
    assert call["market_symbol"] == "SENSEX"
    assert call["option_type"] == "PE"


def test_unknown_identity_fails_closed():
    _, translator = build()
    with pytest.raises(FyersLegacyIdentityResolutionError, match="UNMAPPED"):
        translator("NSE", "UNKNOWN", "999")


def test_duplicate_exchange_token_fails_closed():
    duplicated = rows() + [dict(rows()[0])]
    with pytest.raises(FyersLegacyIdentityResolutionError, match="AMBIGUOUS"):
        FyersLegacyIdentityResolverV2(
            instrument_rows=duplicated,
            resolver=FakeResolver(),
            clock=lambda: NOW,
        )
