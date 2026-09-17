from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.options.fyers_native_option_chain_engine_v2 import (
    FyersNativeOptionChainEngineV2,
)


NOW = datetime(2026, 9, 22, 5, 0, tzinfo=timezone.utc)


class FakeResolver:
    def resolve(self, **kwargs):
        assert kwargs["instrument_type"] == "UNDERLYING"
        return {"provider_symbol": "NSE:NIFTY50-INDEX"}


class FakeProvider:
    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    def __init__(self, rows=None):
        self.calls = []
        self.rows = list(rows or native_rows())

    def get_option_chain(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "provider": "FYERS",
            "rows": tuple(self.rows),
            "request_count": 1,
            "per_contract_depth_requests": 0,
            "data_only": True,
            "live_execution_eligible": False,
        }


def instruments():
    result = []
    for strike in (24950.0, 25000.0, 25050.0):
        for option_type in ("CE", "PE"):
            token = f"{int(strike)}-{option_type}"
            result.append(
                {
                    "market": "NIFTY",
                    "exchange": "NFO",
                    "expiry": "22SEP2026",
                    "strike": strike,
                    "type": option_type,
                    "symbol": f"NIFTY22SEP26{int(strike)}{option_type}",
                    "token": token,
                }
            )
    return result


def provider_symbol(strike, option_type):
    return f"NSE:NIFTY26922{int(strike)}{option_type}"


def identity_resolver(exchange, symbol, token):
    assert exchange == "NFO"
    strike_text, option_type = token.split("-")
    return provider_symbol(float(strike_text), option_type)


def native_rows():
    rows = []
    for index, strike in enumerate((24950.0, 25000.0, 25050.0), start=1):
        rows.extend(
            [
                {
                    "symbol": provider_symbol(strike, "CE"),
                    "strike": strike,
                    "type": "CE",
                    "ltp": 100.0 + index,
                    "oi": 100 * index,
                    "volume": 1000 * index,
                    "bid": 99.5 + index,
                    "ask": 100.5 + index,
                    "token": f"FYCE{index}",
                },
                {
                    "symbol": provider_symbol(strike, "PE"),
                    "strike": strike,
                    "type": "PE",
                    "ltp": 90.0 + index,
                    "oi": 200 * index,
                    "volume": 2000 * index,
                    "bid": 89.5 + index,
                    "ask": 90.5 + index,
                    "token": f"FYPE{index}",
                },
            ]
        )
    rows.append(
        {
            "symbol": "NSE:NIFTY2692925000CE",
            "strike": 25000.0,
            "type": "CE",
            "ltp": 300.0,
            "oi": 9999,
            "volume": 9999,
            "bid": 299.0,
            "ask": 301.0,
            "token": "WRONGEXPIRY",
        }
    )
    return rows


def build(rows=None):
    provider = FakeProvider(rows)
    engine = FyersNativeOptionChainEngineV2(
        market="NIFTY",
        provider=provider,
        resolver=FakeResolver(),
        legacy_identity_resolver=identity_resolver,
        cache_ttl=60,
        native_strike_count=10,
        clock=lambda: NOW,
    )
    return provider, engine


def test_native_chain_uses_one_provider_request_and_zero_depth_fanout():
    provider, engine = build()
    result = engine.fetch("22SEP2026", 25000, instruments(), strike_range=100)
    assert result["status"] == "OK"
    assert len(provider.calls) == 1
    assert provider.calls[0] == {
        "underlying_symbol": "NSE:NIFTY50-INDEX",
        "strike_count": 10,
    }
    assert result["request_count"] == 1
    assert result["per_contract_depth_requests"] == 0


def test_native_cache_reuses_one_raw_chain_for_different_projection_ranges():
    provider, engine = build()
    wide = engine.fetch("22SEP2026", 25000, instruments(), strike_range=100)
    narrow = engine.fetch("22SEP2026", 25000, instruments(), strike_range=50)
    assert wide["status"] == "OK"
    assert narrow["status"] == "OK"
    assert len(provider.calls) == 1
    assert wide["expected_count"] == 6
    assert narrow["expected_count"] == 6


def test_force_refresh_performs_exactly_one_additional_native_request():
    provider, engine = build()
    engine.fetch("22SEP2026", 25000, instruments(), strike_range=100)
    engine.fetch("22SEP2026", 25000, instruments(), strike_range=100, force=True)
    assert len(provider.calls) == 2


def test_native_rows_map_back_to_legacy_contract_identity():
    _, engine = build()
    result = engine.fetch("22SEP2026", 25000, instruments(), strike_range=50)
    ce = result["ce_data"][25000.0]
    assert ce["symbol"] == "NIFTY22SEP2625000CE"
    assert ce["token"] == "25000-CE"
    assert ce["provider_symbol"] == provider_symbol(25000, "CE")
    assert ce["provider_token"] == "FYCE2"


def test_wrong_expiry_provider_row_is_never_attributed_to_requested_contract():
    _, engine = build()
    result = engine.fetch("22SEP2026", 25000, instruments(), strike_range=50)
    assert result["status"] == "OK"
    assert result["matched_count"] == result["expected_count"]
    assert result["identity_mismatch_count"] >= 1
    assert all(
        item["provider_token"] != "WRONGEXPIRY"
        for pool in (result["ce_data"], result["pe_data"])
        for item in pool.values()
    )


def test_complete_identity_mismatch_fails_closed():
    bad_rows = [
        {
            "symbol": "NSE:NIFTY2692925000CE",
            "strike": 25000.0,
            "type": "CE",
            "ltp": 100.0,
            "oi": 1,
            "volume": 1,
            "bid": 99.0,
            "ask": 101.0,
        },
        {
            "symbol": "NSE:NIFTY2692925000PE",
            "strike": 25000.0,
            "type": "PE",
            "ltp": 100.0,
            "oi": 1,
            "volume": 1,
            "bid": 99.0,
            "ask": 101.0,
        },
    ]
    provider, engine = build(bad_rows)
    result = engine.fetch("22SEP2026", 25000, instruments(), strike_range=50)
    assert len(provider.calls) == 1
    assert result["status"] == "EVIDENCE_UNAVAILABLE"
    assert result["reason"] == "NATIVE_EXPIRY_IDENTITY_MISMATCH"
    assert result["matched_count"] == 0
    assert result["per_contract_depth_requests"] == 0


def test_pcr_volume_and_liquidity_fields_are_preserved():
    _, engine = build()
    result = engine.fetch("22SEP2026", 25000, instruments(), strike_range=100)
    assert result["pcr_oi"] == 2.0
    assert result["pcr_volume"] == 2.0
    ce = result["ce_data"][25000.0]
    assert ce["bid"] > 0
    assert ce["ask"] > ce["bid"]
    assert ce["spread_pct"] is not None
    assert ce["bid_ask_source"] == "PROVIDER_OPTION_CHAIN"


def test_missing_expected_contract_is_reported_not_fabricated():
    rows = [row for row in native_rows() if row.get("symbol") != provider_symbol(25050, "PE")]
    _, engine = build(rows)
    result = engine.fetch("22SEP2026", 25000, instruments(), strike_range=100)
    assert result["status"] == "OK"
    assert result["missing_count"] == 1
    assert 25050.0 not in result["pe_data"]


def test_no_expected_contracts_avoids_provider_call():
    provider, engine = build()
    result = engine.fetch("29SEP2026", 25000, instruments(), strike_range=100)
    assert result["status"] == "EVIDENCE_UNAVAILABLE"
    assert result["reason"] == "NO_EXPECTED_CONTRACT_IDENTITIES"
    assert result["request_count"] == 0
    assert provider.calls == []


def test_engine_safety_flags_and_description_are_explicit():
    _, engine = build()
    result = engine.fetch("22SEP2026", 25000, instruments(), strike_range=100)
    assert engine.data_only is True
    assert engine.order_capability_allowed is False
    assert engine.automatic_fallback_allowed is False
    text = engine.describe(result)
    assert "native_req=1" in text
    assert "depth_fanout=0" in text


def test_invalid_market_rejected():
    with pytest.raises(ValueError, match="NIFTY or SENSEX"):
        FyersNativeOptionChainEngineV2(
            market="BANKNIFTY",
            provider=FakeProvider(),
            resolver=FakeResolver(),
            legacy_identity_resolver=identity_resolver,
        )
