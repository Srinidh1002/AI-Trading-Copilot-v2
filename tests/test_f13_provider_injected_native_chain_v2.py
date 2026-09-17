from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from provider_injected_target_bot_v2 import (  # noqa: E402
    ProviderInjectedBotError,
    ProviderInjectedUnifiedTradingBotV2,
)


class SafeDataApi:
    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False


class FakeNativeChain:
    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    def __init__(self, result):
        self.result = result
        self.calls = []

    def fetch(self, expiry, atm, instruments, strike_range):
        self.calls.append((expiry, atm, tuple(instruments), strike_range))
        return self.result


class UnsafeNativeChain(FakeNativeChain):
    order_capability_allowed = True


def runtime():
    return SimpleNamespace(
        provider="FYERS",
        data_only=True,
        order_capability_allowed=False,
        automatic_fallback_allowed=False,
    )


def bare_bot(chain):
    bot = object.__new__(ProviderInjectedUnifiedTradingBotV2)
    bot.market = "NIFTY"
    bot.strike_interval = 50
    bot._native_option_chain_engine = chain
    bot.instruments = [
        {
            "market": "NIFTY",
            "exchange": "NFO",
            "expiry": "22SEP2026",
            "strike": 25000.0,
            "type": "CE",
            "symbol": "NIFTY22SEP2625000CE",
            "token": "CE1",
        },
        {
            "market": "NIFTY",
            "exchange": "NFO",
            "expiry": "22SEP2026",
            "strike": 25000.0,
            "type": "PE",
            "symbol": "NIFTY22SEP2625000PE",
            "token": "PE1",
        },
    ]
    bot._last_chain = None
    return bot


def ok_chain():
    return {
        "status": "OK",
        "provider": "FYERS",
        "pcr_oi": 1.25,
        "request_count": 1,
        "per_contract_depth_requests": 0,
        "ce_data": {
            25000.0: {
                "strike": 25000.0,
                "type": "CE",
                "symbol": "NIFTY22SEP2625000CE",
                "token": "CE1",
                "ltp": 101.5,
                "bid": 101.0,
                "ask": 102.0,
                "oi": 100,
                "volume": 1000,
            }
        },
        "pe_data": {
            25000.0: {
                "strike": 25000.0,
                "type": "PE",
                "symbol": "NIFTY22SEP2625000PE",
                "token": "PE1",
                "ltp": 95.0,
                "bid": 94.5,
                "ask": 95.5,
                "oi": 125,
                "volume": 900,
            }
        },
    }


def test_boundary_accepts_safe_native_chain():
    ProviderInjectedUnifiedTradingBotV2._validate_provider_boundary(
        runtime(), SafeDataApi(), FakeNativeChain(ok_chain())
    )


def test_boundary_rejects_order_capable_native_chain():
    with pytest.raises(ProviderInjectedBotError, match="OPTION_CHAIN_ORDER_CAPABILITY"):
        ProviderInjectedUnifiedTradingBotV2._validate_provider_boundary(
            runtime(), SafeDataApi(), UnsafeNativeChain(ok_chain())
        )


def test_get_options_uses_native_chain_and_persists_provenance():
    chain = FakeNativeChain(ok_chain())
    bot = bare_bot(chain)
    options, atm = bot.get_options(25010.0, "22SEP2026")
    assert atm == 25000
    assert len(options) == 2
    assert bot._last_chain is chain.result
    assert bot._last_chain["pcr_oi"] == 1.25
    assert bot._last_chain["request_count"] == 1
    assert bot._last_chain["per_contract_depth_requests"] == 0
    assert len(chain.calls) == 1


def test_native_chain_failure_is_persisted_and_fails_closed():
    result = {
        "status": "EVIDENCE_UNAVAILABLE",
        "reason": "NATIVE_EXPIRY_IDENTITY_MISMATCH",
        "request_count": 1,
        "per_contract_depth_requests": 0,
    }
    chain = FakeNativeChain(result)
    bot = bare_bot(chain)
    options, atm = bot.get_options(25010.0, "22SEP2026")
    assert atm == 25000
    assert options == []
    assert bot._last_chain is result
    assert bot._last_chain["reason"] == "NATIVE_EXPIRY_IDENTITY_MISMATCH"


def test_missing_expiry_clears_prior_chain_and_avoids_fetch():
    chain = FakeNativeChain(ok_chain())
    bot = bare_bot(chain)
    bot._last_chain = {"status": "OK", "pcr_oi": 9.9}
    options, atm = bot.get_options(25010.0, None)
    assert atm == 25000
    assert options == []
    assert bot._last_chain is None
    assert chain.calls == []


def test_native_option_rows_keep_exact_legacy_identity_for_downstream_trade():
    chain = FakeNativeChain(ok_chain())
    bot = bare_bot(chain)
    options, _ = bot.get_options(25010.0, "22SEP2026")
    ce = next(item for item in options if item["type"] == "CE")
    assert ce["symbol"] == "NIFTY22SEP2625000CE"
    assert ce["token"] == "CE1"
    assert ce["bid"] == 101.0
    assert ce["ask"] == 102.0
