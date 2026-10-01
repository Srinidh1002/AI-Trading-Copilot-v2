from __future__ import annotations

from datetime import UTC, datetime

from services.broker.fyers_streaming_v2 import (
    FyersStreamingDataProviderV2,
)

NOW = datetime(2026, 9, 17, 10, 0, tzinfo=UTC)


class FakeSocket:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.connect_calls = 0

    def connect(self):
        self.connect_calls += 1
        self.kwargs["on_connect"]()

    def subscribe(self, *, symbols, data_type):
        del symbols, data_type

    def unsubscribe(self, *, symbols, data_type):
        del symbols, data_type

    def close_connection(self):
        pass

    def emit(self, message):
        self.kwargs["on_message"](message)

    def reconnect(self):
        self.kwargs["on_close"]("SDK_RECONNECT")
        self.kwargs["on_connect"]()


class SilentConnectSocket(FakeSocket):
    """A socket whose connect() never fires on_connect.

    This models the window between socket construction and transport
    establishment. No observation may be delivered from this window.
    """

    def connect(self):
        self.connect_calls += 1


class CapturingFactory:
    def __init__(self, socket_cls=FakeSocket):
        self._socket_cls = socket_cls
        self.socket = None
        self.kwargs = None
        self.call_count = 0

    def __call__(self, **kwargs):
        self.call_count += 1
        self.kwargs = kwargs
        self.socket = self._socket_cls(**kwargs)
        return self.socket


def instrument(symbol):
    return {
        "provider_symbol": symbol,
        "provider_token": None,
        "canonical_instrument_id": f"NIFTY|UNDERLYING|{symbol}",
        "market_symbol": "NIFTY",
        "instrument_type": "UNDERLYING",
    }


def build():
    factory = CapturingFactory()
    provider = FyersStreamingDataProviderV2(
        access_token="APP-100:RAW_TOKEN",
        client_id="APP-100",
        log_path="TEMP_LOG",
        socket_factory=factory,
        reconnect=True,
        now=lambda: NOW,
    )
    return factory, provider


def build_silent():
    factory = CapturingFactory(socket_cls=SilentConnectSocket)
    provider = FyersStreamingDataProviderV2(
        access_token="APP-100:RAW_TOKEN",
        client_id="APP-100",
        log_path="TEMP_LOG",
        socket_factory=factory,
        reconnect=True,
        now=lambda: NOW,
    )
    return factory, provider


def test_emitted_record_carries_connection_generation():
    factory, provider = build()
    received = []
    provider.subscribe((instrument("NSE:NIFTY50-INDEX"),), received.append)
    assert provider.wait_until_connected(1.0)
    factory.socket.emit({"symbol": "NSE:NIFTY50-INDEX", "ltp": 23456.0})
    assert len(received) == 1
    assert received[0]["connection_generation"] == 1
    provider.close()


def test_reconnect_bumps_generation_in_emitted_records():
    factory, provider = build()
    received = []
    provider.subscribe((instrument("NSE:NIFTY50-INDEX"),), received.append)
    assert provider.wait_until_connected(1.0)
    factory.socket.emit({"symbol": "NSE:NIFTY50-INDEX", "ltp": 1.0})
    factory.socket.reconnect()
    factory.socket.emit({"symbol": "NSE:NIFTY50-INDEX", "ltp": 2.0})
    assert [r["connection_generation"] for r in received] == [1, 2]
    provider.close()


def test_message_from_foreign_socket_instance_is_dropped():
    factory, provider = build()
    received = []
    provider.subscribe((instrument("NSE:NIFTY50-INDEX"),), received.append)
    assert provider.wait_until_connected(1.0)

    # A second socket built from the same kwargs was never registered
    # as provider._socket. Its callback path must not reach consumers.
    foreign = FakeSocket(**factory.kwargs)
    provider._on_message_for_socket(
        foreign,
        {"symbol": "NSE:NIFTY50-INDEX", "ltp": 999.0},
    )
    assert received == []
    provider.close()


def test_message_after_close_is_dropped():
    factory, provider = build()
    received = []
    provider.subscribe((instrument("NSE:NIFTY50-INDEX"),), received.append)
    assert provider.wait_until_connected(1.0)
    provider.close()
    factory.socket.emit({"symbol": "NSE:NIFTY50-INDEX", "ltp": 1.0})
    assert received == []


def test_message_before_subscription_is_dropped():
    factory, provider = build_silent()
    received = []
    provider.subscribe((instrument("NSE:NIFTY50-INDEX"),), received.append)
    # SilentConnectSocket never fires on_connect, so transport is not
    # connected, no subscription is active, and the provider must not
    # be considered ready.
    provider._on_message_for_socket(
        factory.socket,
        {"symbol": "NSE:NIFTY50-INDEX", "ltp": 100.0},
    )
    snapshot = provider.snapshot()
    assert received == []
    assert snapshot["connected"] is False
    assert snapshot["transport_connected"] is False
    assert snapshot["subscribed"] is False
    provider.close()


def test_ready_implies_transport_and_subscription():
    factory, provider = build()
    provider.subscribe((instrument("NSE:NIFTY50-INDEX"),), lambda item: None)
    assert provider.wait_until_connected(1.0)
    snapshot = provider.snapshot()
    assert snapshot["connected"] is True
    assert snapshot["transport_connected"] is True
    assert snapshot["subscribed"] is True
    provider.close()


def test_close_clears_ready_flags():
    factory, provider = build()
    provider.subscribe((instrument("NSE:NIFTY50-INDEX"),), lambda item: None)
    assert provider.wait_until_connected(1.0)
    provider.close()
    snapshot = provider.snapshot()
    assert snapshot["connected"] is False
    assert snapshot["transport_connected"] is False
    assert snapshot["subscribed"] is False
    assert snapshot["closed"] is True


def test_callback_from_closed_provider_does_not_resurrect_state():
    factory, provider = build()
    received = []
    provider.subscribe((instrument("NSE:NIFTY50-INDEX"),), received.append)
    assert provider.wait_until_connected(1.0)
    provider.close()
    provider._on_message_for_socket(
        factory.socket,
        {"symbol": "NSE:NIFTY50-INDEX", "ltp": 5.0},
    )
    assert received == []
