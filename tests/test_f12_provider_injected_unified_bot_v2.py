from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import MethodType, SimpleNamespace

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from provider_injected_target_bot_v2 import (  # noqa: E402
    ProviderInjectedBotError,
    ProviderInjectedUnifiedTradingBotV2,
)
from target_focused_bot import UnifiedTradingBot  # noqa: E402


class SafeDataApi:
    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False


class UnsafeDataApi(SafeDataApi):
    order_capability_allowed = True


class FakeResolver:
    def resolve(self, **kwargs):
        return {
            "provider_symbol": "NSE:NIFTY50-INDEX",
            "provider_token": None,
            "market_symbol": kwargs["market_symbol"],
            "instrument_type": kwargs["instrument_type"],
        }


class FakeStreaming:
    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    def __init__(self):
        self.calls = []
        self.unsubscribe_calls = []

    def subscribe(self, instruments, callback):
        self.calls.append(tuple(instruments))
        callback(
            {
                "provider_symbol": "NSE:NIFTY50-INDEX",
                "ltp": 23270.5,
                "ts": datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc),
            }
        )
        return "sub-1"

    def wait_until_connected(self, timeout):
        return True

    def unsubscribe(self, subscription_id):
        self.unsubscribe_calls.append(subscription_id)

    def is_healthy(self, max_age):
        return True

    def snapshot(self):
        return {"connected": True}


class FakeCandleBuilder:
    def __init__(self):
        self.calls = []

    def on_tick(self, token, ltp, ts):
        self.calls.append((token, ltp, ts))


def runtime(**overrides):
    values = dict(
        provider="FYERS",
        data_only=True,
        order_capability_allowed=False,
        automatic_fallback_allowed=False,
        resolver=FakeResolver(),
        streaming=FakeStreaming(),
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def bare_bot():
    bot = object.__new__(ProviderInjectedUnifiedTradingBotV2)
    bot.market = "NIFTY"
    bot.index_token = "99926000"
    bot._provider_runtime = runtime()
    bot._provider_subscription_id = None
    bot.candle_builder = FakeCandleBuilder()
    bot.ws_healthy = False
    bot.ws_feed = None
    bot.is_connected = False
    bot.option_chain_engine = object()
    bot.provider_option_chain_status = None
    return bot


def test_provider_injected_bot_is_real_unified_bot_subclass():
    assert issubclass(ProviderInjectedUnifiedTradingBotV2, UnifiedTradingBot)


def test_boundary_accepts_fyers_data_only_runtime():
    ProviderInjectedUnifiedTradingBotV2._validate_provider_boundary(
        runtime(), SafeDataApi()
    )


def test_boundary_rejects_non_fyers_runtime():
    with pytest.raises(ProviderInjectedBotError, match="FYERS_RUNTIME_REQUIRED"):
        ProviderInjectedUnifiedTradingBotV2._validate_provider_boundary(
            runtime(provider="ANGEL_SMARTAPI"), SafeDataApi()
        )


def test_boundary_rejects_order_capable_runtime_or_data_api():
    with pytest.raises(ProviderInjectedBotError, match="ORDER_CAPABILITY"):
        ProviderInjectedUnifiedTradingBotV2._validate_provider_boundary(
            runtime(order_capability_allowed=True), SafeDataApi()
        )
    with pytest.raises(ProviderInjectedBotError, match="ORDER_CAPABILITY"):
        ProviderInjectedUnifiedTradingBotV2._validate_provider_boundary(
            runtime(), UnsafeDataApi()
        )


def test_boundary_rejects_automatic_fallback():
    with pytest.raises(ProviderInjectedBotError, match="FALLBACK_PROHIBITED"):
        ProviderInjectedUnifiedTradingBotV2._validate_provider_boundary(
            runtime(automatic_fallback_allowed=True), SafeDataApi()
        )


def test_connect_override_never_enters_angel_auth_path():
    bot = bare_bot()
    calls = []

    bot.check_connection = MethodType(lambda self: True, bot)
    bot._initialize_provider_engines = MethodType(
        lambda self: calls.append("engines"), bot
    )
    bot._start_websocket = MethodType(
        lambda self: calls.append("stream"), bot
    )

    assert bot.connect_with_retry(max_retries=1, retry_delay=0) is True
    assert bot.is_connected is True
    assert calls == ["engines", "stream"]


def test_reconnect_uses_provider_safe_override():
    bot = bare_bot()
    bot.check_connection = MethodType(lambda self: False, bot)
    bot.connect_with_retry = MethodType(
        lambda self, max_retries=3, retry_delay=10: True, bot
    )
    assert bot.reconnect_if_needed() is True


def test_stream_subscription_feeds_existing_candle_builder():
    bot = bare_bot()
    bot._start_websocket()
    assert bot._provider_subscription_id == "sub-1"
    assert bot.ws_healthy is True
    assert len(bot.candle_builder.calls) == 1
    token, ltp, ts = bot.candle_builder.calls[0]
    assert token == "99926000"
    assert ltp == 23270.5
    assert ts.tzinfo is not None
    assert bot.ws_feed.health_str() == "HEALTHY"


def test_stream_close_unsubscribes_without_closing_shared_provider():
    bot = bare_bot()
    stream = bot._provider_runtime.streaming
    bot._start_websocket()
    bot.close_provider_subscription()
    assert stream.unsubscribe_calls == ["sub-1"]
    assert bot.ws_feed is None
    assert bot.ws_healthy is False


def test_engine_init_explicitly_blocks_legacy_option_chain_until_f13():
    bot = bare_bot()
    sentinel = object()
    bot.market_intel = sentinel
    bot.vix_engine = sentinel
    bot.calendar_engine = sentinel
    bot.news_engine = sentinel
    bot.fii_dii_engine = sentinel
    bot.external_intel = sentinel
    bot.prev_day_engine = sentinel
    bot.rate_limiter = sentinel
    bot.obj = SafeDataApi()
    bot.index_exchange = "NSE"

    bot._initialize_provider_engines()

    assert bot.option_chain_engine is None
    assert bot.provider_option_chain_status == "F13_NATIVE_OPTION_CHAIN_REQUIRED"


def test_injected_class_preserves_paper_only_class_boundary():
    assert ProviderInjectedUnifiedTradingBotV2.data_only is True
    assert ProviderInjectedUnifiedTradingBotV2.order_capability_allowed is False
    assert ProviderInjectedUnifiedTradingBotV2.automatic_fallback_allowed is False


def test_f12_source_contains_no_angel_auth_or_order_surface():
    text = (SRC / "provider_injected_target_bot_v2.py").read_text(encoding="utf-8")
    forbidden = (
        "SmartConnect(",
        "generateSession(",
        "getfeedToken(",
        "placeOrder",
        "place_order",
        "submit_order",
        "FyersOrderSocket",
        "order_ws",
    )
    assert not [marker for marker in forbidden if marker in text]
