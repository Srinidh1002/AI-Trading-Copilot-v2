"""Tests for normal and certification Angel market-data clients."""
from __future__ import annotations

from services.broker import shared_client


class _FakeController:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _FakeClient:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.request_controller = kwargs.get(
            "request_controller"
        )
        self.__class__.instances.append(self)


def setup_function():
    _FakeClient.instances.clear()
    shared_client.reset_shared_market_clients_for_testing()


def teardown_function():
    shared_client.reset_shared_market_clients_for_testing()


def test_normal_client_remains_one_shared_singleton(
    monkeypatch,
):
    monkeypatch.setattr(
        shared_client,
        "AngelMarketDataClient",
        _FakeClient,
    )

    first = shared_client.get_market_client()
    second = shared_client.get_market_client()

    assert first is second
    assert len(_FakeClient.instances) == 1
    assert first.kwargs == {}


def test_certification_client_has_deterministic_retry_policy(
    monkeypatch,
):
    monkeypatch.setattr(
        shared_client,
        "AngelMarketDataClient",
        _FakeClient,
    )
    monkeypatch.setattr(
        shared_client,
        "MarketDataRequestController",
        _FakeController,
    )

    client = (
        shared_client
        .get_certification_market_client()
    )

    assert client.kwargs["max_retries"] == 1
    assert (
        client.kwargs[
            "max_rate_limit_retries"
        ]
        == 0
    )

    controller = client.request_controller

    assert (
        controller.kwargs[
            "historical_request_interval_seconds"
        ]
        == 1.0
    )
    assert (
        controller.kwargs[
            "historical_requests_per_second"
        ]
        == 1
    )
    assert (
        controller.kwargs[
            "historical_requests_per_minute"
        ]
        == 120
    )
    assert (
        controller.kwargs[
            "historical_requests_per_hour"
        ]
        == 4000
    )


def test_certification_client_is_one_shared_singleton(
    monkeypatch,
):
    monkeypatch.setattr(
        shared_client,
        "AngelMarketDataClient",
        _FakeClient,
    )
    monkeypatch.setattr(
        shared_client,
        "MarketDataRequestController",
        _FakeController,
    )

    first = (
        shared_client
        .get_certification_market_client()
    )
    second = (
        shared_client
        .get_certification_market_client()
    )

    assert first is second
    assert len(_FakeClient.instances) == 1


def test_normal_and_certification_clients_are_isolated(
    monkeypatch,
):
    monkeypatch.setattr(
        shared_client,
        "AngelMarketDataClient",
        _FakeClient,
    )
    monkeypatch.setattr(
        shared_client,
        "MarketDataRequestController",
        _FakeController,
    )

    normal = shared_client.get_market_client()
    certification = (
        shared_client
        .get_certification_market_client()
    )

    assert normal is not certification
    assert len(_FakeClient.instances) == 2
    assert normal.kwargs == {}
    assert certification.kwargs[
        "max_rate_limit_retries"
    ] == 0


def test_reset_discards_both_singletons(
    monkeypatch,
):
    monkeypatch.setattr(
        shared_client,
        "AngelMarketDataClient",
        _FakeClient,
    )
    monkeypatch.setattr(
        shared_client,
        "MarketDataRequestController",
        _FakeController,
    )

    first_normal = shared_client.get_market_client()
    first_certification = (
        shared_client
        .get_certification_market_client()
    )

    shared_client.reset_shared_market_clients_for_testing()

    second_normal = shared_client.get_market_client()
    second_certification = (
        shared_client
        .get_certification_market_client()
    )

    assert first_normal is not second_normal
    assert (
        first_certification
        is not second_certification
    )
