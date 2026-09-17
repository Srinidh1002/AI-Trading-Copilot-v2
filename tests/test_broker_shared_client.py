"""Tests for shared Angel market-data clients and account-wide pacing."""
from __future__ import annotations

from services.broker import shared_client


class _FakeController:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.__class__.instances.append(self)


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
    _FakeController.instances.clear()

    shared_client.reset_shared_market_clients_for_testing()


def teardown_function():
    shared_client.reset_shared_market_clients_for_testing()


def _patch_dependencies(monkeypatch):
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


def test_request_controller_is_one_shared_singleton(
    monkeypatch,
):
    _patch_dependencies(monkeypatch)

    first = (
        shared_client
        .get_shared_request_controller()
    )
    second = (
        shared_client
        .get_shared_request_controller()
    )

    assert first is second
    assert len(_FakeController.instances) == 1

    assert first.kwargs == {
        "historical_request_interval_seconds": 1.0,
        "historical_requests_per_second": 1,
        "historical_requests_per_minute": 120,
        "historical_requests_per_hour": 4000,
        "market_quote_request_interval_seconds": 1.0,
    }


def test_normal_client_remains_one_shared_singleton(
    monkeypatch,
):
    _patch_dependencies(monkeypatch)

    first = shared_client.get_market_client()
    second = shared_client.get_market_client()

    assert first is second
    assert len(_FakeClient.instances) == 1

    assert (
        first.request_controller
        is shared_client.get_shared_request_controller()
    )


def test_certification_client_has_deterministic_retry_policy(
    monkeypatch,
):
    _patch_dependencies(monkeypatch)

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

    assert (
        client.request_controller
        is shared_client.get_shared_request_controller()
    )


def test_certification_client_is_one_shared_singleton(
    monkeypatch,
):
    _patch_dependencies(monkeypatch)

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


def test_normal_and_certification_clients_are_distinct_but_share_budget(
    monkeypatch,
):
    _patch_dependencies(monkeypatch)

    normal = shared_client.get_market_client()

    certification = (
        shared_client
        .get_certification_market_client()
    )

    assert normal is not certification
    assert len(_FakeClient.instances) == 2

    assert (
        normal.request_controller
        is certification.request_controller
    )

    assert (
        normal.request_controller
        is shared_client.get_shared_request_controller()
    )

    assert (
        certification.kwargs[
            "max_rate_limit_retries"
        ]
        == 0
    )

    assert certification.kwargs[
        "max_retries"
    ] == 1


def test_construction_order_does_not_change_shared_budget(
    monkeypatch,
):
    _patch_dependencies(monkeypatch)

    certification = (
        shared_client
        .get_certification_market_client()
    )

    normal = shared_client.get_market_client()

    assert (
        certification.request_controller
        is normal.request_controller
    )

    assert len(_FakeController.instances) == 1


def test_reset_discards_clients_and_shared_controller(
    monkeypatch,
):
    _patch_dependencies(monkeypatch)

    first_normal = (
        shared_client.get_market_client()
    )
    first_certification = (
        shared_client
        .get_certification_market_client()
    )
    first_controller = (
        shared_client
        .get_shared_request_controller()
    )

    shared_client.reset_shared_market_clients_for_testing()

    second_normal = (
        shared_client.get_market_client()
    )
    second_certification = (
        shared_client
        .get_certification_market_client()
    )
    second_controller = (
        shared_client
        .get_shared_request_controller()
    )

    assert first_normal is not second_normal

    assert (
        first_certification
        is not second_certification
    )

    assert (
        first_controller
        is not second_controller
    )

    assert (
        second_normal.request_controller
        is second_controller
    )

    assert (
        second_certification.request_controller
        is second_controller
    )
