from __future__ import annotations

from datetime import UTC, datetime

import pytest

from services.options.fyers_certified_option_chain_builder_v2 import (
    FyersCertifiedOptionChainBuilderV2,
    FyersCertifiedOptionChainError,
    FyersCertifiedTwoIndexOptionChainBuilderV2,
)


NOW = datetime(2026, 10, 5, 7, 0, tzinfo=UTC)


class FakeProvider:
    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    def __init__(self, *, rows=None, request_count=1, depth_fanout=0):
        self.calls = []
        self.request_count = request_count
        self.depth_fanout = depth_fanout
        self.rows = list(rows if rows is not None else self.default_rows())

    @staticmethod
    def default_rows():
        rows = []
        for strike in (22400.0, 22450.0, 22500.0):
            rows.extend(
                [
                    {
                        "symbol": f"NSE:NIFTY26O06{int(strike)}CE",
                        "strike": strike,
                        "type": "CE",
                        "ltp": 100.0,
                        "oi": 1000,
                        "oich": 10,
                        "prev_oi": 990,
                        "volume": 5000,
                        "bid": 99.5,
                        "ask": 100.5,
                    },
                    {
                        "symbol": f"NSE:NIFTY26O06{int(strike)}PE",
                        "strike": strike,
                        "type": "PE",
                        "ltp": 95.0,
                        "oi": 1200,
                        "oich": 12,
                        "prev_oi": 1188,
                        "volume": 4500,
                        "bid": 94.5,
                        "ask": 95.5,
                    },
                ]
            )
        return rows

    def get_option_chain(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "provider": "FYERS",
            "rows": tuple(self.rows),
            "request_count": self.request_count,
            "per_contract_depth_requests": self.depth_fanout,
            "expiry_data": (
                {"date": "2026-10-06", "expiry": 1791243000},
                {"date": "2026-10-27", "expiry": 1793053800},
            ),
        }


class FakeResolver:
    def __init__(self):
        self.calls = []

    def resolve(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["instrument_type"] == "UNDERLYING":
            return {
                "provider_symbol": "NSE:NIFTY50-INDEX",
                "provider": "FYERS",
            }
        strike = float(kwargs["strike"])
        option_type = kwargs["option_type"]
        return {
            "provider_symbol": f"NSE:NIFTY26O06{int(strike)}{option_type}",
            "provider_token": f"FY-{int(strike)}-{option_type}",
            "lot_size": 65,
            "tick_size": 0.05,
            "provider": "FYERS",
        }


def build(provider=None, resolver=None):
    provider = provider or FakeProvider()
    resolver = resolver or FakeResolver()
    builder = FyersCertifiedOptionChainBuilderV2(
        market="NIFTY",
        provider=provider,
        resolver=resolver,
        clock=lambda: NOW,
    )
    return provider, resolver, builder


def test_builds_certified_shape_from_one_native_request():
    provider, resolver, builder = build()

    chain = builder.build_chain(
        "NIFTY",
        22462.0,
        strikes_each_side=1,
        option_exchange="NFO",
    )

    assert len(provider.calls) == 1
    assert provider.calls[0] == {
        "underlying_symbol": "NSE:NIFTY50-INDEX",
        "strike_count": 5,
    }
    assert chain["provider"] == "FYERS"
    assert chain["expiry"] == "2026-10-06"
    assert chain["request_count"] == 1
    assert chain["per_contract_depth_requests"] == 0
    assert chain["data_only"] is True
    assert chain["live_execution_eligible"] is False
    assert len(chain["contracts"]) == 6
    assert {row["option_type"] for row in chain["contracts"]} == {"CE", "PE"}
    assert all(row["lot_size"] == 65 for row in chain["contracts"])
    assert all(row["tick_size"] == 0.05 for row in chain["contracts"])
    assert all(row["provider"] == "FYERS" for row in chain["contracts"])
    assert len([c for c in resolver.calls if c["instrument_type"] == "OPTION"]) == 6


def test_provider_symbol_mismatch_fails_closed():
    class BadResolver(FakeResolver):
        def resolve(self, **kwargs):
            result = super().resolve(**kwargs)
            if kwargs["instrument_type"] == "OPTION":
                result["provider_symbol"] = "NSE:WRONG"
            return result

    _, _, builder = build(resolver=BadResolver())

    with pytest.raises(
        FyersCertifiedOptionChainError,
        match="FYERS_OPTION_IDENTITY_MISMATCH",
    ):
        builder.build_chain("NIFTY", 22462.0, option_exchange="NFO")


def test_missing_verified_lot_size_fails_closed():
    class BadResolver(FakeResolver):
        def resolve(self, **kwargs):
            result = super().resolve(**kwargs)
            if kwargs["instrument_type"] == "OPTION":
                result["lot_size"] = None
            return result

    _, _, builder = build(resolver=BadResolver())

    with pytest.raises(
        FyersCertifiedOptionChainError,
        match="OPTION_LOT_SIZE_UNVERIFIED",
    ):
        builder.build_chain("NIFTY", 22462.0, option_exchange="NFO")


def test_depth_fanout_is_prohibited():
    _, _, builder = build(provider=FakeProvider(depth_fanout=1))

    with pytest.raises(
        FyersCertifiedOptionChainError,
        match="FYERS_OPTION_DEPTH_FANOUT_PROHIBITED",
    ):
        builder.build_chain("NIFTY", 22462.0, option_exchange="NFO")


def test_one_sided_chain_is_rejected():
    rows = [
        row
        for row in FakeProvider.default_rows()
        if row["type"] == "CE"
    ]
    _, _, builder = build(provider=FakeProvider(rows=rows))

    with pytest.raises(
        FyersCertifiedOptionChainError,
        match="FYERS_OPTION_TWO_SIDED_CHAIN_REQUIRED",
    ):
        builder.build_chain("NIFTY", 22462.0, option_exchange="NFO")


def test_market_identity_is_strict():
    _, _, builder = build()
    with pytest.raises(
        FyersCertifiedOptionChainError,
        match="UNDERLYING_IDENTITY_MISMATCH",
    ):
        builder.build_chain("SENSEX", 22462.0, option_exchange="NFO")

    with pytest.raises(
        FyersCertifiedOptionChainError,
        match="OPTION_EXCHANGE_IDENTITY_MISMATCH",
    ):
        builder.build_chain("NIFTY", 22462.0, option_exchange="BFO")


def test_two_index_dispatcher_routes_nifty_without_changing_contract():
    provider = FakeProvider()
    resolver = FakeResolver()
    dispatcher = FyersCertifiedTwoIndexOptionChainBuilderV2(
        provider=provider,
        resolver=resolver,
        clock=lambda: NOW,
    )
    chain = dispatcher.build_chain(
        "NIFTY",
        22462.0,
        strikes_each_side=1,
        option_exchange="NFO",
    )
    assert chain["provider"] == "FYERS"
    assert chain["underlying"] == "NIFTY"
    assert len(provider.calls) == 1


def test_two_index_dispatcher_rejects_non_index_market():
    dispatcher = FyersCertifiedTwoIndexOptionChainBuilderV2(
        provider=FakeProvider(),
        resolver=FakeResolver(),
        clock=lambda: NOW,
    )
    with pytest.raises(
        FyersCertifiedOptionChainError,
        match="UNSUPPORTED_CERTIFIED_INDEX_MARKET",
    ):
        dispatcher.build_chain(
            "CRUDEOILM",
            7000.0,
            option_exchange="MCX",
        )
