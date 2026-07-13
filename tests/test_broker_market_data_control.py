import logging
from unittest.mock import MagicMock, patch

import pytest

from services.broker.angel_client import AngelMarketDataClient
from services.broker.market_data_control import (
    BrokerMarketDataRequestError,
    MarketDataRequestController,
)


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


def _response():
    return {
        "status": True,
        "data": {"fetched": [{"symbolToken": "99926000", "ltp": 25000.0}]},
    }


def _client(**kwargs):
    with patch("services.broker.angel_client.SmartConnect") as smart_connect:
        api = MagicMock()
        smart_connect.return_value = api
        client = AngelMarketDataClient(
            retry_delay_seconds=0,
            min_request_interval_seconds=0,
            historical_request_interval_seconds=0,
            rate_limit_cooldown_seconds=0,
            **kwargs,
        )
    client.authenticated = True
    client.session = {"status": True}
    return client, api


def test_market_data_reuses_short_lived_identical_response():
    client, api = _client(cache_ttl_seconds=5)
    api.getMarketData.return_value = _response()

    first = client.get_market_data("LTP", {"NSE": ["99926000"]})
    second = client.get_market_data("LTP", {"NSE": ["99926000"]})

    assert api.getMarketData.call_count == 1
    assert first == second
    assert first is not second


def test_rate_limit_is_not_misclassified_as_authentication_and_retries_once():
    client, api = _client(max_rate_limit_retries=1)
    api.getMarketData.side_effect = [
        {"status": False, "message": "Access denied because of exceeding access rate"},
        _response(),
    ]
    client.login = MagicMock()

    result = client.get_market_data("LTP", {"NSE": ["99926000"]})

    assert result["status"] is True
    assert api.getMarketData.call_count == 2
    client.login.assert_not_called()


def test_rate_limit_failure_is_bounded_and_structured():
    client, api = _client(max_rate_limit_retries=1)
    api.getMarketData.return_value = {
        "status": False,
        "message": "Access denied because of exceeding access rate",
    }

    with pytest.raises(BrokerMarketDataRequestError) as raised:
        client.get_market_data("LTP", {"NSE": ["99926000"]})

    assert api.getMarketData.call_count == 2
    assert raised.value.failure == {
        "request_name": "market-data",
        "attempts": 2,
        "failure_type": "rate_limited",
        "detail": "Access denied because of exceeding access rate",
    }


def test_controller_spaces_consecutive_outbound_requests():
    clock = FakeClock()
    controller = MarketDataRequestController(
        min_request_interval_seconds=1,
        cache_ttl_seconds=0,
        monotonic_function=clock.monotonic,
        sleep_function=clock.sleep,
    )

    controller.wait_for_slot("market-data", 1)
    clock.value = 0.25
    wait = controller.wait_for_slot("market-data", 1)

    assert wait == 0.75
    assert clock.value == 1.0


def test_historical_request_has_stricter_endpoint_pacing_after_spot():
    clock = FakeClock()
    controller = MarketDataRequestController(
        min_request_interval_seconds=1,
        historical_request_interval_seconds=5,
        cache_ttl_seconds=0,
        rate_limit_cooldown_seconds=0,
        monotonic_function=clock.monotonic,
        sleep_function=clock.sleep,
    )

    controller.wait_for_slot("market-data", 1)
    wait = controller.wait_for_slot("historical-data", 1)

    assert wait == 5
    assert clock.value == 5


def test_rate_limit_starts_global_exponential_cooldown():
    clock = FakeClock()
    controller = MarketDataRequestController(
        min_request_interval_seconds=0,
        historical_request_interval_seconds=0,
        cache_ttl_seconds=0,
        rate_limit_cooldown_seconds=10,
        monotonic_function=clock.monotonic,
        sleep_function=clock.sleep,
    )

    controller.wait_for_slot("historical-data", 1)
    assert controller.record_rate_limit("historical-data", 1, 2) == 10
    wait = controller.wait_for_slot("market-data", 2)
    assert wait == 10
    assert controller.record_rate_limit("market-data", 2, 2) == 20


def test_rate_limited_client_waits_for_controller_cooldown_before_retry():
    clock = FakeClock()
    controller = MarketDataRequestController(
        min_request_interval_seconds=0,
        historical_request_interval_seconds=0,
        cache_ttl_seconds=0,
        rate_limit_cooldown_seconds=10,
        monotonic_function=clock.monotonic,
        sleep_function=clock.sleep,
    )
    client, api = _client(
        request_controller=controller,
        max_rate_limit_retries=1,
    )
    api.getCandleData.side_effect = [
        {"status": False, "message": "Access denied because of exceeding access rate"},
        {"status": True, "data": [["2026-07-13 10:00", 1, 2, 1, 2, 10]]},
    ]

    response = client.get_historical_data(
        "NSE", "99926000", "FIVE_MINUTE", "2026-07-13 09:00", "2026-07-13 10:00"
    )

    assert response["status"] is True
    assert api.getCandleData.call_count == 2
    assert clock.value == 10


def test_controller_logs_request_timing_and_cache_outcome(caplog):
    clock = FakeClock()
    controller = MarketDataRequestController(
        min_request_interval_seconds=0,
        historical_request_interval_seconds=0,
        cache_ttl_seconds=1,
        rate_limit_cooldown_seconds=0,
        monotonic_function=clock.monotonic,
        sleep_function=clock.sleep,
    )
    caplog.set_level(logging.INFO, logger="services.broker.market_data_control")

    assert controller.get_cached(("safe-key",), "market-data") is None
    controller.wait_for_slot("market-data", 1)
    controller.cache(("safe-key",), _response())
    assert controller.get_cached(("safe-key",), "market-data")["status"] is True

    messages = "\n".join(caplog.messages)
    assert "request_type=market-data" in messages
    assert "monotonic=" in messages
    assert "attempt=1" in messages
    assert "wait_applied_seconds=" in messages
    assert "cache=miss" in messages
    assert "cache=hit" in messages


def test_completed_authentication_becomes_the_next_request_pacing_boundary():
    clock = FakeClock()
    controller = MarketDataRequestController(
        min_request_interval_seconds=2,
        historical_request_interval_seconds=0,
        cache_ttl_seconds=0,
        rate_limit_cooldown_seconds=0,
        monotonic_function=clock.monotonic,
        sleep_function=clock.sleep,
    )

    controller.wait_for_slot("authentication", 1)
    clock.value = 3
    controller.mark_request_complete("authentication")
    wait = controller.wait_for_slot("market-data", 1)

    assert wait == 2
    assert clock.value == 5
