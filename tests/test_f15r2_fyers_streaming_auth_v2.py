"""F15-R2 Phases R2-10 / R2-11 \u2014 FYERS DataSocket auth + reconnect.

Complements tests/test_f9_fyers_streaming_v2.py. This file adds the
cases R2-10/R2-11 require which f9 did not assert:

R2-10:
  * missing / empty / whitespace / non-string token fails closed
  * no token value appears in stdout or stderr during construction,
    subscribe, or reconnect
  * the adapter clears its own _access_token after socket construction
R2-11:
  * the qualified token is what the factory receives
  * reconnect (SDK-driven via FakeSocket.reconnect) does not
    reconstruct the socket \u2014 factory is called exactly once
  * the reconnect path does not print the token
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from services.broker.fyers_streaming_v2 import (  # noqa: E402
    FyersStreamingConfigurationError,
    FyersStreamingDataProviderV2,
)

NOW = datetime(2026, 9, 17, 10, 0, tzinfo=UTC)
SECRET = "APP-100:SECRET_VALUE_XYZ"
RAW = "RAW_TOKEN_XYZ"


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
        """Simulate the official SDK's internal reconnect: on_close then on_connect."""
        self.kwargs["on_close"]("SDK_RECONNECT")
        self.kwargs["on_connect"]()


class CapturingFactory:
    def __init__(self):
        self.socket = None
        self.kwargs = None
        self.call_count = 0

    def __call__(self, **kwargs):
        self.call_count += 1
        self.kwargs = kwargs
        self.socket = FakeSocket(**kwargs)
        return self.socket


def instrument(symbol):
    return {
        "provider_symbol": symbol,
        "provider_token": None,
        "canonical_instrument_id": f"NIFTY|UNDERLYING|{symbol}",
        "market_symbol": "NIFTY",
        "instrument_type": "UNDERLYING",
    }


def build(*, access_token=SECRET, client_id="APP-100"):
    factory = CapturingFactory()
    provider = FyersStreamingDataProviderV2(
        access_token=access_token,
        client_id=client_id,
        log_path="TEMP_LOG",
        socket_factory=factory,
        reconnect=True,
        now=lambda: NOW,
    )
    return factory, provider


# ---------- R2-10: auth fail-closed ----------

def test_missing_token_fails_closed():
    with pytest.raises(FyersStreamingConfigurationError):
        FyersStreamingDataProviderV2(
            access_token="",
            client_id="APP-100",
            log_path="TEMP_LOG",
            socket_factory=CapturingFactory(),
        )


def test_whitespace_token_fails_closed():
    with pytest.raises(FyersStreamingConfigurationError):
        FyersStreamingDataProviderV2(
            access_token="   \t  ",
            client_id="APP-100",
            log_path="TEMP_LOG",
            socket_factory=CapturingFactory(),
        )


def test_none_token_fails_closed():
    with pytest.raises(FyersStreamingConfigurationError):
        FyersStreamingDataProviderV2(
            access_token=None,  # type: ignore[arg-type]
            client_id="APP-100",
            log_path="TEMP_LOG",
            socket_factory=CapturingFactory(),
        )


def test_non_string_token_fails_closed():
    with pytest.raises(FyersStreamingConfigurationError):
        FyersStreamingDataProviderV2(
            access_token=42,  # type: ignore[arg-type]
            client_id="APP-100",
            log_path="TEMP_LOG",
            socket_factory=CapturingFactory(),
        )


def test_empty_log_path_fails_closed():
    with pytest.raises(FyersStreamingConfigurationError):
        FyersStreamingDataProviderV2(
            access_token=SECRET,
            client_id="APP-100",
            log_path="",
            socket_factory=CapturingFactory(),
        )


# ---------- R2-10: no secret in stdout/stderr ----------

def test_no_token_in_stdout_during_construction(capsys):
    factory, provider = build(access_token=SECRET)
    captured = capsys.readouterr()
    assert "SECRET_VALUE_XYZ" not in captured.out
    assert "SECRET_VALUE_XYZ" not in captured.err
    assert SECRET not in captured.out
    assert SECRET not in captured.err
    provider.close()


def test_no_token_in_stdout_during_subscribe(capsys):
    factory, provider = build(access_token=SECRET)
    provider.subscribe((instrument("NSE:NIFTY50-INDEX"),), lambda item: None)
    provider.wait_until_connected(1.0)
    captured = capsys.readouterr()
    assert "SECRET_VALUE_XYZ" not in captured.out
    assert "SECRET_VALUE_XYZ" not in captured.err
    provider.close()


def test_no_token_in_stdout_during_reconnect(capsys):
    factory, provider = build(access_token=SECRET)
    provider.subscribe((instrument("NSE:NIFTY50-INDEX"),), lambda item: None)
    provider.wait_until_connected(1.0)
    factory.socket.reconnect()
    captured = capsys.readouterr()
    assert "SECRET_VALUE_XYZ" not in captured.out
    assert "SECRET_VALUE_XYZ" not in captured.err
    provider.close()


# ---------- R2-10: adapter clears its own copy of the token ----------

def test_adapter_clears_access_token_after_socket_construction():
    factory, provider = build(access_token=SECRET)
    provider.subscribe((instrument("NSE:NIFTY50-INDEX"),), lambda item: None)
    provider.wait_until_connected(1.0)
    # The adapter must clear its private token after handing it to the
    # official SDK so it cannot leak via instance introspection.
    assert provider._access_token == ""
    provider.close()


# ---------- R2-11: reconnect semantics ----------

def test_initial_connect_passes_qualified_token_to_factory():
    factory = CapturingFactory()
    provider = FyersStreamingDataProviderV2(
        access_token=RAW,
        client_id="APP-100",
        log_path="TEMP_LOG",
        socket_factory=factory,
        reconnect=True,
        now=lambda: NOW,
    )
    provider.subscribe((instrument("NSE:NIFTY50-INDEX"),), lambda item: None)
    provider.wait_until_connected(1.0)
    # The factory must receive the qualified form APP-100:RAW_TOKEN
    assert factory.kwargs["access_token"] == f"APP-100:{RAW}"
    provider.close()


def test_reconnect_does_not_rebuild_socket():
    factory, provider = build()
    provider.subscribe((instrument("NSE:NIFTY50-INDEX"),), lambda item: None)
    provider.wait_until_connected(1.0)
    assert factory.call_count == 1
    # Simulate the official SDK's internal reconnect
    factory.socket.reconnect()
    # The adapter must not construct a second socket: reconnect is
    # handled internally by the official SDK on the same instance.
    assert factory.call_count == 1
    provider.close()


def test_reconnect_preserves_connection_generation_bump():
    factory, provider = build()
    provider.subscribe((instrument("NSE:NIFTY50-INDEX"),), lambda item: None)
    provider.wait_until_connected(1.0)
    gen_before = provider._connection_generation
    factory.socket.reconnect()
    gen_after = provider._connection_generation
    # _on_connect increments the generation on every connect, including
    # SDK-driven reconnects. This is how downstream consumers detect a
    # fresh authentication session.
    assert gen_after == gen_before + 1
    provider.close()
