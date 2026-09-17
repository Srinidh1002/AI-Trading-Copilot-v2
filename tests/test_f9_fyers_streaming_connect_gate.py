from __future__ import annotations

from datetime import datetime, timezone

from services.broker.fyers_streaming_v2 import FyersStreamingDataProviderV2


NOW = datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc)


class FailingSocket:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.close_calls = 0

    def connect(self):
        self.kwargs["on_connect"]()

    def subscribe(self, *, symbols, data_type):
        raise RuntimeError("subscription rejected")

    def unsubscribe(self, *, symbols, data_type):
        return None

    def close_connection(self):
        self.close_calls += 1


class FailingFactory:
    def __init__(self):
        self.socket = None

    def __call__(self, **kwargs):
        self.socket = FailingSocket(**kwargs)
        return self.socket


def test_connected_gate_waits_for_successful_physical_subscription():
    factory = FailingFactory()
    provider = FyersStreamingDataProviderV2(
        access_token="APP-100:RAW_TOKEN",
        client_id="APP-100",
        log_path="TEMP_LOG",
        socket_factory=factory,
        reconnect=True,
        now=lambda: NOW,
    )

    provider.subscribe(
        ({"provider_symbol": "NSE:NIFTY50-INDEX"},),
        lambda item: None,
    )

    assert provider.wait_until_connected(0.05) is False
    snapshot = provider.snapshot()
    assert snapshot["connected"] is False
    assert snapshot["error_count"] == 1
    assert str(snapshot["last_error"]).startswith("resubscribe:")

    provider.close()
    assert factory.socket.close_calls == 1
