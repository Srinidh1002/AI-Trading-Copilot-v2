from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from services.broker.fyers_streaming_v2 import (
    FyersStreamingConfigurationError,
    FyersStreamingDataProviderV2,
    FyersStreamingSubscriptionError,
)
from services.broker.provider_data_interfaces_v2 import (
    StreamingMarketDataProviderV2,
)
from services.contracts.provider_runtime_bundle_v2 import (
    ProviderRuntimeBundleV2,
)


NOW = datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc)


class FakeSocket:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.connect_calls = 0
        self.subscribe_calls = []
        self.unsubscribe_calls = []
        self.close_calls = 0

    def connect(self):
        self.connect_calls += 1
        self.kwargs["on_connect"]()

    def subscribe(self, *, symbols, data_type):
        self.subscribe_calls.append((tuple(symbols), data_type))

    def unsubscribe(self, *, symbols, data_type):
        self.unsubscribe_calls.append((tuple(symbols), data_type))

    def close_connection(self):
        self.close_calls += 1

    def emit(self, message):
        self.kwargs["on_message"](message)

    def reconnect(self):
        self.kwargs["on_close"]("test")
        self.kwargs["on_connect"]()


class CapturingFactory:
    def __init__(self):
        self.socket = None
        self.kwargs = None

    def __call__(self, **kwargs):
        self.kwargs = kwargs
        self.socket = FakeSocket(**kwargs)
        return self.socket


def instrument(symbol, *, token=None, market="NIFTY", instrument_type="UNDERLYING"):
    return {
        "provider_symbol": symbol,
        "provider_token": token,
        "canonical_instrument_id": f"{market}|{instrument_type}|{symbol}",
        "market_symbol": market,
        "instrument_type": instrument_type,
    }


def build(*, now=lambda: NOW, access_token="APP-100:RAW_TOKEN"):
    factory = CapturingFactory()
    provider = FyersStreamingDataProviderV2(
        access_token=access_token,
        client_id="APP-100",
        log_path="TEMP_LOG",
        socket_factory=factory,
        reconnect=True,
        now=now,
    )
    return factory, provider


def test_streaming_adapter_satisfies_v2_protocol():
    _, provider = build()
    assert isinstance(provider, StreamingMarketDataProviderV2)
    provider.close()


def test_raw_token_is_qualified_for_data_socket():
    factory, provider = build(access_token="RAW_TOKEN")
    provider.subscribe((instrument("NSE:NIFTY50-INDEX"),), lambda item: None)
    assert provider.wait_until_connected(1.0)
    assert factory.kwargs["access_token"] == "APP-100:RAW_TOKEN"
    assert factory.kwargs["litemode"] is False
    assert factory.kwargs["write_to_file"] is False
    assert factory.kwargs["reconnect"] is True
    provider.close()


def test_unqualified_token_requires_explicit_client_id():
    with pytest.raises(FyersStreamingConfigurationError):
        FyersStreamingDataProviderV2(
            access_token="RAW_TOKEN",
            client_id=None,
            log_path="TEMP_LOG",
            socket_factory=CapturingFactory(),
        )


def test_first_subscription_starts_one_socket_and_symbolupdate():
    factory, provider = build()
    sid = provider.subscribe(
        (
            instrument("NSE:NIFTY50-INDEX"),
            instrument("BSE:SENSEX-INDEX"),
        ),
        lambda item: None,
    )
    assert sid == "fyers-stream-1"
    assert provider.wait_until_connected(1.0)
    assert factory.socket.connect_calls == 1
    assert factory.socket.subscribe_calls == [
        (("BSE:SENSEX-INDEX", "NSE:NIFTY50-INDEX"), "SymbolUpdate")
    ]
    provider.close()


def test_tick_normalizes_token_ltp_and_timezone_aware_ts():
    factory, provider = build()
    received = []
    provider.subscribe(
        (instrument("NSE:NIFTY50-INDEX", token="FY-NIFTY"),), received.append
    )
    assert provider.wait_until_connected(1.0)
    factory.socket.emit(
        {
            "symbol": "NSE:NIFTY50-INDEX",
            "ltp": 23456.75,
            "timestamp": 1789639200,
            "type": "symbolUpdate",
        }
    )
    assert len(received) == 1
    tick = received[0]
    assert tick["provider"] == "FYERS"
    assert tick["provider_symbol"] == "NSE:NIFTY50-INDEX"
    assert tick["provider_token"] == "FY-NIFTY"
    assert tick["token"] == "FY-NIFTY"
    assert tick["token_source"] == "RESOLVED_INSTRUMENT"
    assert tick["ltp"] == 23456.75
    assert tick["ts"].tzinfo is not None
    assert tick["timestamp_source"] == "PROVIDER"
    assert tick["data_only"] is True
    assert tick["live_execution_eligible"] is False
    provider.close()


def test_provider_fytoken_has_precedence_over_instrument_token():
    factory, provider = build()
    received = []
    provider.subscribe(
        (instrument("NSE:NIFTY50-INDEX", token="MASTER-TOKEN"),), received.append
    )
    assert provider.wait_until_connected(1.0)
    factory.socket.emit(
        {
            "symbol": "NSE:NIFTY50-INDEX",
            "ltp": 23456.0,
            "fyToken": "LIVE-FY-TOKEN",
        }
    )
    assert received[0]["token"] == "LIVE-FY-TOKEN"
    assert received[0]["token_source"] == "PROVIDER_TOKEN"
    provider.close()


def test_missing_provider_timestamp_uses_local_receipt_explicitly():
    factory, provider = build()
    received = []
    provider.subscribe((instrument("NSE:NIFTY50-INDEX"),), received.append)
    assert provider.wait_until_connected(1.0)
    factory.socket.emit({"symbol": "NSE:NIFTY50-INDEX", "ltp": "23456.25"})
    assert received[0]["ts"] == NOW
    assert received[0]["timestamp_source"] == "LOCAL_RECEIPT"
    provider.close()


def test_control_and_invalid_price_messages_do_not_reach_consumer():
    factory, provider = build()
    received = []
    provider.subscribe((instrument("NSE:NIFTY50-INDEX"),), received.append)
    assert provider.wait_until_connected(1.0)
    factory.socket.emit({"type": "cn", "s": "ok"})
    factory.socket.emit({"symbol": "NSE:NIFTY50-INDEX", "ltp": 0})
    assert received == []
    provider.close()


def test_overlapping_consumers_share_one_physical_symbol_subscription():
    factory, provider = build()
    first = []
    second = []
    first_sid = provider.subscribe(
        (instrument("NSE:NIFTY50-INDEX"),), first.append
    )
    assert provider.wait_until_connected(1.0)
    second_sid = provider.subscribe(
        (instrument("NSE:NIFTY50-INDEX"),), second.append
    )
    assert len(factory.socket.subscribe_calls) == 1
    factory.socket.emit({"symbol": "NSE:NIFTY50-INDEX", "ltp": 23457})
    assert len(first) == 1
    assert len(second) == 1
    provider.unsubscribe(first_sid)
    assert factory.socket.unsubscribe_calls == []
    provider.unsubscribe(second_sid)
    assert factory.socket.unsubscribe_calls == [
        (("NSE:NIFTY50-INDEX",), "SymbolUpdate")
    ]
    provider.close()


def test_new_symbol_on_connected_socket_is_subscribed_incrementally():
    factory, provider = build()
    provider.subscribe((instrument("NSE:NIFTY50-INDEX"),), lambda item: None)
    assert provider.wait_until_connected(1.0)
    provider.subscribe(
        (instrument("BSE:SENSEX-INDEX", market="SENSEX"),), lambda item: None
    )
    assert factory.socket.subscribe_calls[-1] == (
        ("BSE:SENSEX-INDEX",),
        "SymbolUpdate",
    )
    provider.close()


def test_reconnect_resubscribes_current_unique_symbol_set():
    factory, provider = build()
    provider.subscribe(
        (
            instrument("NSE:NIFTY50-INDEX"),
            instrument("BSE:SENSEX-INDEX", market="SENSEX"),
        ),
        lambda item: None,
    )
    assert provider.wait_until_connected(1.0)
    factory.socket.reconnect()
    assert factory.socket.subscribe_calls[-1] == (
        ("BSE:SENSEX-INDEX", "NSE:NIFTY50-INDEX"),
        "SymbolUpdate",
    )
    assert provider.snapshot()["connection_generation"] == 2
    provider.close()


def test_callback_failure_isolated_from_other_consumers():
    factory, provider = build()
    good = []

    def bad(_):
        raise RuntimeError("consumer failed")

    provider.subscribe((instrument("NSE:NIFTY50-INDEX"),), bad)
    provider.subscribe((instrument("NSE:NIFTY50-INDEX"),), good.append)
    assert provider.wait_until_connected(1.0)
    factory.socket.emit({"symbol": "NSE:NIFTY50-INDEX", "ltp": 23458})
    assert len(good) == 1
    assert provider.snapshot()["callback_error_count"] == 1
    provider.close()


def test_health_requires_connected_and_fresh_real_tick():
    clock = {"now": NOW}
    factory, provider = build(now=lambda: clock["now"])
    provider.subscribe((instrument("NSE:NIFTY50-INDEX"),), lambda item: None)
    assert provider.wait_until_connected(1.0)
    assert provider.is_healthy(30) is False
    factory.socket.emit({"symbol": "NSE:NIFTY50-INDEX", "ltp": 23459})
    assert provider.is_healthy(30) is True
    clock["now"] = NOW + timedelta(seconds=31)
    assert provider.is_healthy(30) is False
    provider.close()


def test_symbol_limit_fails_before_second_subscription_mutates_state():
    _, provider = build()
    many = tuple(instrument(f"NSE:TEST{i}-EQ") for i in range(200))
    provider.subscribe(many, lambda item: None)
    assert provider.wait_until_connected(1.0)
    with pytest.raises(
        FyersStreamingSubscriptionError,
        match="FYERS_STREAM_SYMBOL_LIMIT_EXCEEDED",
    ):
        provider.subscribe((instrument("NSE:OVER-LIMIT"),), lambda item: None)
    assert provider.snapshot()["desired_symbol_count"] == 200
    provider.close()


def test_invalid_subscription_fails_closed():
    _, provider = build()
    with pytest.raises(FyersStreamingSubscriptionError):
        provider.subscribe(({"market_symbol": "NIFTY"},), lambda item: None)
    with pytest.raises(TypeError):
        provider.subscribe((instrument("NSE:NIFTY50-INDEX"),), None)
    provider.close()


def test_close_is_idempotent_and_closes_one_data_socket():
    factory, provider = build()
    provider.subscribe((instrument("NSE:NIFTY50-INDEX"),), lambda item: None)
    assert provider.wait_until_connected(1.0)
    provider.close()
    provider.close()
    assert factory.socket.close_calls == 1
    assert provider.snapshot()["closed"] is True


class FakeResolver:
    def resolve(self, **kwargs):
        return {"provider_symbol": "TEST"}


class FakeHistorical:
    def get_candles(self, instrument, *, interval, start, end):
        return []


class FakeQuoteDepth:
    def get_quote(self, instrument):
        return {}

    def get_depth(self, instrument):
        return {}


class FakeController:
    def wait_for_slot(self, request_type, attempt):
        return 0.0

    def record_rate_limit(self, request_type, retry_number, backoff_multiplier):
        return 0.0

    def record_success(self, request_type):
        return None


def test_streaming_adapter_is_valid_runtime_bundle_component():
    _, provider = build()
    bundle = ProviderRuntimeBundleV2(
        provider="FYERS",
        resolver=FakeResolver(),
        historical=FakeHistorical(),
        quote_depth=FakeQuoteDepth(),
        streaming=provider,
        request_controller=FakeController(),
    )
    assert bundle.streaming is provider
    assert bundle.data_only is True
    assert bundle.order_capability_allowed is False
    assert bundle.automatic_fallback_allowed is False
    provider.close()


def test_f9_module_exposes_no_order_socket_or_order_methods():
    path = Path("services/broker/fyers_streaming_v2.py")
    text = path.read_text(encoding="utf-8")
    forbidden = (
        "FyersOrderSocket",
        "order_ws",
        "place_order",
        "placeOrder",
        "modify_order",
        "cancel_order",
        "submit_order",
    )
    assert not [marker for marker in forbidden if marker in text]
