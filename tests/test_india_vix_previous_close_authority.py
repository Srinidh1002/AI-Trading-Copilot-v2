from datetime import datetime, timedelta, timezone

import pytest

from services.contracts.india_vix_previous_close_policy_v1 import (
    DEFAULT_INDIA_VIX_PREVIOUS_CLOSE_POLICY,
    IndiaVixPreviousClosePolicyV1,
)
from services.paper_orchestration.india_vix_live_reader import (
    IndiaVixLiveReader,
)


NOW = datetime(2026, 8, 3, 10, 0, tzinfo=timezone.utc)


def master():
    return [
        {
            "token": "99926017",
            "symbol": "India VIX",
            "name": "INDIA VIX",
            "exch_seg": "NSE",
            "instrumenttype": "AMXIDX",
        }
    ]


class Client:
    def __init__(self, row):
        self.row = row
        self.calls = 0

    def get_market_data(self, mode, exchange_tokens):
        self.calls += 1
        assert mode == "FULL"
        assert exchange_tokens == {"NSE": ["99926017"]}
        return {
            "status": True,
            "data": {"fetched": [self.row]},
        }


def row(**changes):
    value = {
        "ltp": 15.2,
        "close": 14.8,
        "previousClose": 999.0,
        "tradingSymbol": "India VIX",
        "symbolToken": "99926017",
        "exchange": "NSE",
        "exchFeedTime": "2026-08-03T09:59:30+00:00",
    }
    value.update(changes)
    return value


def reader(
    provider_row=None,
    *,
    times=(NOW, NOW),
    policy=DEFAULT_INDIA_VIX_PREVIOUS_CLOSE_POLICY,
):
    values = iter(times)
    client = Client(provider_row or row())
    value = IndiaVixLiveReader(
        master_fetcher=master,
        market_client=client,
        clock=lambda: next(values),
        previous_close_policy=policy,
    )
    return value, client


def test_policy_uses_only_certified_close_field():
    value, field, blockers = (
        DEFAULT_INDIA_VIX_PREVIOUS_CLOSE_POLICY.resolve(row())
    )
    assert value == 14.8
    assert field == "close"
    assert blockers == ()


def test_previous_close_field_is_not_accepted_as_fallback():
    provider_row = row(close=None, previousClose=14.7)
    value, field, blockers = (
        DEFAULT_INDIA_VIX_PREVIOUS_CLOSE_POLICY.resolve(provider_row)
    )
    assert value is None
    assert field is None
    assert blockers == ("INDIA_VIX_PREVIOUS_CLOSE_UNAVAILABLE",)


@pytest.mark.parametrize("bad", (None, 0, -1, True, "14.8"))
def test_invalid_certified_close_fails_closed(bad):
    value, field, blockers = (
        DEFAULT_INDIA_VIX_PREVIOUS_CLOSE_POLICY.resolve(
            row(close=bad)
        )
    )
    assert value is None
    assert field is None
    assert blockers == ("INDIA_VIX_PREVIOUS_CLOSE_UNAVAILABLE",)


def test_reader_preserves_previous_close_policy_provenance():
    value, client = reader()
    result = value.capture("cycle-1")

    assert result.source_status == "READY"
    assert result.current_value == 15.2
    assert result.previous_close == 14.8
    assert result.metadata["previous_close_source_field"] == "close"
    assert result.metadata["previous_close_policy_id"] == (
        DEFAULT_INDIA_VIX_PREVIOUS_CLOSE_POLICY.policy_id
    )
    assert result.metadata["provider_timestamp_field"] == (
        "exchFeedTime"
    )
    assert client.calls == 1


def test_missing_certified_close_is_unavailable_not_substituted():
    value, _ = reader(row(close=None, previousClose=14.7))
    result = value.capture("cycle-1")

    assert result.source_status == "UNAVAILABLE"
    assert result.current_value is None
    assert result.previous_close is None
    assert result.blockers == (
        "INDIA_VIX_PREVIOUS_CLOSE_UNAVAILABLE",
    )


def test_stale_and_future_quotes_fail_closed():
    stale, _ = reader(
        row(exchFeedTime="2026-08-03T09:50:00+00:00")
    )
    assert stale.capture("stale").source_status == "STALE"

    future_time = NOW + timedelta(seconds=10)
    future, _ = reader(
        row(exchFeedTime=future_time.isoformat())
    )
    assert future.capture("future").source_status == "STALE"


def test_exactly_once_capture_per_cycle():
    value, client = reader()
    first = value.capture("cycle-1")
    second = value.capture("cycle-1")

    assert first is second
    assert client.calls == 1
    assert value.master_resolution_count == 1
    assert value.quote_count == 1


def test_wrong_policy_type_is_rejected():
    with pytest.raises(TypeError):
        IndiaVixLiveReader(
            master_fetcher=master,
            market_client=Client(row()),
            clock=lambda: NOW,
            previous_close_policy=object(),
        )


def test_policy_contract_is_locked_and_deterministic():
    policy = IndiaVixPreviousClosePolicyV1()
    assert policy.to_json() == policy.to_json()

    with pytest.raises(ValueError):
        IndiaVixPreviousClosePolicyV1(
            primary_provider_field="previousClose"
        )
    with pytest.raises(ValueError):
        IndiaVixPreviousClosePolicyV1(
            permitted_fallback_fields=("previousClose",)
        )
