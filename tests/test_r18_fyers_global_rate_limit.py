from __future__ import annotations

import pytest

from services.broker.fyers_sdk_data_client_v2 import (
    FyersDataOnlySdkFacadeV2,
    build_fyers_data_client_v2,
)


class FakeLimiter:
    def __init__(self):
        self.waits = []
        self.rate_limits = []

    def wait_if_needed(self, endpoint="default"):
        self.waits.append(endpoint)
        return True

    def record_rate_limit(self, endpoint="default"):
        self.rate_limits.append(endpoint)
        return 5.0


class FakeRaw:
    def __init__(self):
        self.calls = []
        self.responses = {}
        self.exceptions = {}

    def _call(self, name, data):
        self.calls.append((name, data))
        if name in self.exceptions:
            raise self.exceptions[name]
        return self.responses.get(name, {"s": "ok", "name": name})

    def quotes(self, data=None):
        return self._call("quotes", data)

    def depth(self, data=None):
        return self._call("depth", data)

    def history(self, data=None):
        return self._call("history", data)

    def optionchain(self, data=None):
        return self._call("optionchain", data)

    def futures_chain(self, data=None):
        return self._call("futures_chain", data)

    def expiry_dates(self, data=None):
        return self._call("expiry_dates", data)

    def fno_historical_data(self, data=None):
        return self._call("fno_historical_data", data)


@pytest.mark.parametrize(
    "method_name",
    (
        "quotes",
        "depth",
        "history",
        "optionchain",
        "futures_chain",
        "expiry_dates",
        "fno_historical_data",
    ),
)
def test_every_sdk_surface_consumes_global_permit(method_name):
    raw = FakeRaw()
    limiter = FakeLimiter()
    client = FyersDataOnlySdkFacadeV2(raw, rate_limiter=limiter)

    result = getattr(client, method_name)({"probe": method_name})

    assert result["s"] == "ok"
    assert limiter.waits == [method_name]
    assert raw.calls == [(method_name, {"probe": method_name})]


def test_provider_429_response_records_shared_cooldown_without_retry():
    raw = FakeRaw()
    raw.responses["history"] = {
        "s": "error",
        "code": 429,
        "message": "request limit reached",
    }
    limiter = FakeLimiter()
    client = FyersDataOnlySdkFacadeV2(raw, rate_limiter=limiter)

    result = client.history({"symbol": "MCX:TEST"})

    assert result["code"] == 429
    assert limiter.waits == ["history"]
    assert limiter.rate_limits == ["history"]
    assert len(raw.calls) == 1


def test_provider_429_exception_records_shared_cooldown_and_reraises():
    raw = FakeRaw()
    raw.exceptions["depth"] = RuntimeError("HTTP 429 request limit reached")
    limiter = FakeLimiter()
    client = FyersDataOnlySdkFacadeV2(raw, rate_limiter=limiter)

    with pytest.raises(RuntimeError, match="429"):
        client.depth({"symbol": "MCX:TEST"})

    assert limiter.waits == ["depth"]
    assert limiter.rate_limits == ["depth"]
    assert len(raw.calls) == 1


def test_builder_accepts_injected_limiter():
    limiter = FakeLimiter()
    created = []

    def factory(**kwargs):
        created.append(kwargs)
        return FakeRaw()

    client = build_fyers_data_client_v2(
        client_id="APP-100",
        access_token="TOKEN",
        log_path="LOG",
        model_factory=factory,
        rate_limiter=limiter,
    )

    client.quotes({"symbols": "NSE:NIFTY50-INDEX"})

    assert limiter.waits == ["quotes"]
    assert created[0]["token"] == "TOKEN"
