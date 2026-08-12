from datetime import datetime, time
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from services.market.live_multi_timeframe_data import (
    LiveMultiTimeframeData,
    required_closed_candle_at,
)
from services.market_session.policies import MarketSessionPolicy
from services.market_session.validator import validate_session_timestamp


def candle_data():
    return {
        "status": True,
        "data": [
            [
                "2026-07-10T09:15:00+05:30",
                24124.7,
                24187.9,
                24120.35,
                24162.7,
                0,
            ],
            [
                "2026-07-10T09:20:00+05:30",
                24162.7,
                24190.0,
                24150.0,
                24180.0,
                0,
            ],
        ],
    }


def make_cache():
    cache = MagicMock()

    cache.get.return_value = None

    return cache


@pytest.mark.parametrize(
    ("exchange", "expected_start"),
    (
        ("NSE", time(15, 25)),
        ("BSE", time(15, 25)),
        ("NFO", time(15, 35)),
        ("BFO", time(15, 35)),
    ),
)
def test_after_hours_closed_candle_uses_exchange_historical_close(
    exchange,
    expected_start,
):
    result = required_closed_candle_at(
        "5m",
        datetime(2026, 7, 10, 16, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
        exchange=exchange,
    )

    assert result.time() == expected_start


def test_historical_intraday_and_previous_session_boundaries_remain_exchange_aware():
    assert required_closed_candle_at(
        "5m",
        datetime(2026, 7, 10, 10, 17, tzinfo=ZoneInfo("Asia/Kolkata")),
        exchange="NSE",
    ).time() == time(10, 10)
    assert required_closed_candle_at(
        "5m",
        datetime(2026, 1, 26, 10, 17, tzinfo=ZoneInfo("Asia/Kolkata")),
        exchange="NSE",
    ) == datetime(2026, 1, 23, 15, 25, tzinfo=ZoneInfo("Asia/Kolkata"))


def test_unknown_historical_exchange_fails_closed():
    with pytest.raises(ValueError, match="unsupported historical candle exchange"):
        required_closed_candle_at(
            "5m",
            datetime(2026, 7, 10, 16, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
            exchange="UNKNOWN",
        )


def test_task9_execution_session_policy_remains_fno_authority():
    policy = MarketSessionPolicy()
    assert policy.new_entry_cutoff == time(15, 20)
    assert policy.regular_close == time(15, 40)

    result = validate_session_timestamp(
        symbol="NIFTY",
        exchange="NSE",
        market_timestamp=datetime(2026, 7, 10, 15, 35, tzinfo=ZoneInfo("Asia/Kolkata")),
        evaluated_at=datetime(2026, 7, 10, 15, 35, tzinfo=ZoneInfo("Asia/Kolkata")),
        validation_mode="STRICT_EXECUTION",
        id_factory=lambda: "historical-session-separation",
    )
    assert result.session_state == "REGULAR"

    post_close = validate_session_timestamp(
        symbol="NIFTY",
        exchange="NSE",
        market_timestamp=datetime(2026, 7, 10, 15, 41, tzinfo=ZoneInfo("Asia/Kolkata")),
        evaluated_at=datetime(2026, 7, 10, 15, 41, tzinfo=ZoneInfo("Asia/Kolkata")),
        validation_mode="STRICT_EXECUTION",
        id_factory=lambda: "historical-session-separation-post-close",
    )
    assert post_close.session_state == "POST_CLOSE"


def test_fetch_single_timeframe():

    mock_client = MagicMock()

    mock_client.get_historical_data.return_value = (
        candle_data()
    )

    cache = make_cache()

    service = LiveMultiTimeframeData(
        client=mock_client,
        cache=cache,
    )

    assert service.cache is cache
    mock_client.get_historical_data.assert_not_called()

    result = service.fetch_timeframe(
        exchange="NSE",
        symboltoken="99926000",
        timeframe="5m",
        end_time=datetime(
            2026,
            7,
            10,
            15,
            30,
        ),
    )

    assert isinstance(
        result,
        pd.DataFrame,
    )

    assert len(result) == 2

    assert list(result.columns) == [
        "timestamp",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    assert (
        mock_client
        .get_historical_data
        .call_count
        == 1
    )

    cache.set.assert_called_once()


def test_fetch_all_timeframes():

    mock_client = MagicMock()

    mock_client.get_historical_data.return_value = (
        candle_data()
    )

    cache = make_cache()

    service = LiveMultiTimeframeData(
        client=mock_client,
        cache=cache,
    )

    result = service.fetch_all(
        exchange="NSE",
        symboltoken="99926000",
        end_time=datetime(
            2026,
            7,
            10,
            15,
            30,
        ),
    )

    assert set(result.keys()) == {
        "5m",
        "15m",
        "1h",
        "1d",
    }

    assert (
        mock_client
        .get_historical_data
        .call_count
        == 4
    )

    assert (
        cache.set.call_count
        == 4
    )


def test_fresh_cache_avoids_broker_request():

    mock_client = MagicMock()

    cache = MagicMock()

    cache.get.return_value = (
        candle_data()
    )

    service = LiveMultiTimeframeData(
        client=mock_client,
        cache=cache,
    )

    result = service.fetch_timeframe(
        exchange="NSE",
        symboltoken="99926000",
        timeframe="5m",
    )

    assert isinstance(
        result,
        pd.DataFrame,
    )

    assert len(result) == 2

    mock_client.get_historical_data.assert_not_called()

    cache.set.assert_not_called()


def test_cache_disabled_always_uses_broker():

    mock_client = MagicMock()

    mock_client.get_historical_data.return_value = (
        candle_data()
    )

    cache = MagicMock()

    service = LiveMultiTimeframeData(
        client=mock_client,
        cache=cache,
        cache_enabled=False,
    )

    service.fetch_timeframe(
        exchange="NSE",
        symboltoken="99926000",
        timeframe="5m",
        end_time=datetime(
            2026,
            7,
            10,
            15,
            30,
        ),
    )

    cache.get.assert_not_called()

    cache.set.assert_not_called()

    assert (
        mock_client
        .get_historical_data
        .call_count
        == 1
    )


def test_invalid_timeframe():

    mock_client = MagicMock()

    service = LiveMultiTimeframeData(
        client=mock_client,
        cache=make_cache(),
    )

    with pytest.raises(
        ValueError,
        match="Unsupported timeframe",
    ):
        service.fetch_timeframe(
            exchange="NSE",
            symboltoken="99926000",
            timeframe="2m",
        )


def test_empty_api_data_is_not_cached():

    mock_client = MagicMock()

    mock_client.get_historical_data.return_value = {
        "status": True,
        "data": [],
    }

    cache = make_cache()

    service = LiveMultiTimeframeData(
        client=mock_client,
        cache=cache,
    )

    with pytest.raises(
        ValueError,
        match="No candle data returned",
    ):
        service.fetch_timeframe(
            exchange="NSE",
            symboltoken="99926000",
            timeframe="5m",
        )

    cache.set.assert_not_called()


class MetadataCache:
    def __init__(
        self,
        result=None,
    ):
        self.result = result
        self.set_calls = []

    def get_with_metadata(
        self,
        exchange,
        symboltoken,
        timeframe,
        *,
        max_age_seconds,
        required_until=None,
    ):
        return self.result

    def set(
        self,
        exchange,
        symboltoken,
        timeframe,
        response,
        *,
        source,
        requested_until=None,
    ):
        self.set_calls.append(
            {
                "exchange": exchange,
                "symboltoken": symboltoken,
                "timeframe": timeframe,
                "response": response,
                "source": source,
            }
        )

        return response


class ClosedCoverageMetadataCache(MetadataCache):
    def __init__(self, result=None):
        super().__init__(result=result)
        self.required_closed_at = None

    def get_with_metadata(
        self,
        exchange,
        symboltoken,
        timeframe,
        *,
        max_age_seconds,
        required_until=None,
        required_closed_at=None,
    ):
        self.required_closed_at = required_closed_at
        return self.result


class KwargsMetadataCache(MetadataCache):
    def __init__(self, result=None):
        super().__init__(result=result)
        self.reader_kwargs = None

    def get_with_metadata(
        self,
        exchange,
        symboltoken,
        timeframe,
        **kwargs,
    ):
        self.reader_kwargs = kwargs
        return self.result


class InternalTypeErrorMetadataCache(MetadataCache):
    def __init__(self, result=None):
        super().__init__(result=result)
        self.calls = 0

    def get_with_metadata(
        self,
        exchange,
        symboltoken,
        timeframe,
        *,
        max_age_seconds,
        required_until=None,
        required_closed_at=None,
    ):
        self.calls += 1
        raise TypeError("cache implementation failure")


def test_capture_metadata_preserves_persistent_cache_provenance(
    monkeypatch,
):
    cached = candle_data()

    cache = MetadataCache(
        result={
            "response": cached,
            "metadata": {
                "cache_status": "HIT",
                "cache_source": (
                    "ANGEL_ONE_HISTORICAL"
                ),
                "cache_key": (
                    "NSE:99926000:5m"
                ),
                "cached_at_epoch_seconds": (
                    1000.0
                ),
                "read_at_epoch_seconds": (
                    1060.0
                ),
                "age_seconds": 60.0,
                "max_age_seconds": 240.0,
                "expires_at_epoch_seconds": (
                    1240.0
                ),
                "expired": False,
            },
        }
    )

    client = MagicMock()

    service = LiveMultiTimeframeData(
        client=client,
        cache=cache,
    )

    monkeypatch.setattr(
        "services.market.live_multi_timeframe_data.TIMEFRAME_CONFIG",
        {
            "5m": {
                "interval": "FIVE_MINUTE",
                "lookback_days": 3,
            }
        },
    )

    result = service.fetch_all_with_capture(
        exchange="NSE",
        symboltoken="99926000",
        end_time=datetime(
            2026,
            7,
            10,
            15,
            30,
        ),
    )

    metadata = result[
        "cache_metadata"
    ][
        "5m"
    ]

    assert metadata["cache_status"] == "HIT"
    assert metadata["age_seconds"] == 60.0

    assert (
        metadata["cache_source"]
        == "ANGEL_ONE_HISTORICAL"
    )

    assert (
        metadata["provider_source"]
        == "ANGEL_ONE_HISTORICAL"
    )

    assert (
        metadata["cache_write_status"]
        == "NOT_REQUIRED"
    )

    client.get_historical_data.assert_not_called()
    assert cache.set_calls == []


def test_live_capture_reports_cache_miss_and_write(
    monkeypatch,
):
    client = MagicMock()

    client.get_historical_data.return_value = (
        candle_data()
    )

    cache = MetadataCache(
        result=None
    )

    service = LiveMultiTimeframeData(
        client=client,
        cache=cache,
    )

    monkeypatch.setattr(
        "services.market.live_multi_timeframe_data.TIMEFRAME_CONFIG",
        {
            "5m": {
                "interval": "FIVE_MINUTE",
                "lookback_days": 3,
            }
        },
    )

    result = service.fetch_all_with_capture(
        exchange="NSE",
        symboltoken="99926000",
        end_time=datetime(
            2026,
            7,
            10,
            15,
            30,
        ),
    )

    metadata = result[
        "cache_metadata"
    ][
        "5m"
    ]

    assert metadata["cache_status"] == "MISS"

    assert (
        metadata["provider_source"]
        == "ANGEL_ONE_HISTORICAL"
    )

    assert (
        metadata["cache_write_status"]
        == "WRITTEN"
    )

    assert metadata["age_seconds"] == 0.0
    assert metadata["expired"] is False

    assert len(cache.set_calls) == 1

    assert (
        cache.set_calls[0]["source"]
        == "ANGEL_ONE_HISTORICAL"
    )


def test_invalid_live_candles_are_not_persisted():
    client = MagicMock()

    client.get_historical_data.return_value = {
        "status": True,
        "data": [
            [
                "2026-07-10T09:15:00",
                100,
                101,
                99,
                100,
                10,
            ]
        ],
    }

    cache = MetadataCache(
        result=None
    )

    service = LiveMultiTimeframeData(
        client=client,
        cache=cache,
    )

    with pytest.raises(
        ValueError,
        match="timestamp",
    ):
        service.fetch_timeframe(
            exchange="NSE",
            symboltoken="99926000",
            timeframe="5m",
            end_time=datetime(
                2026,
                7,
                10,
                15,
                30,
            ),
        )

    assert cache.set_calls == []


def test_legacy_metadata_cache_uses_naive_end_time_contract():
    cache = MetadataCache()
    client = MagicMock()
    client.get_historical_data.return_value = candle_data()

    service = LiveMultiTimeframeData(client=client, cache=cache)

    service.fetch_timeframe_raw(
        exchange="NSE",
        symboltoken="99926000",
        timeframe="5m",
        end_time=datetime(2026, 7, 10, 15, 30),
    )

    assert len(cache.set_calls) == 1


def test_legacy_metadata_cache_uses_aware_end_time_contract():
    cache = MetadataCache()
    client = MagicMock()
    client.get_historical_data.return_value = candle_data()

    service = LiveMultiTimeframeData(client=client, cache=cache)

    service.fetch_timeframe_raw(
        exchange="NSE",
        symboltoken="99926000",
        timeframe="5m",
        end_time=datetime(2026, 7, 10, 15, 30, tzinfo=ZoneInfo("Asia/Kolkata")),
    )

    assert len(cache.set_calls) == 1


def test_closed_coverage_cache_receives_required_closed_at():
    cache = ClosedCoverageMetadataCache()
    client = MagicMock()
    client.get_historical_data.return_value = candle_data()

    service = LiveMultiTimeframeData(client=client, cache=cache)

    service.fetch_timeframe_raw(
        exchange="NSE",
        symboltoken="99926000",
        timeframe="5m",
        end_time=datetime(2026, 7, 10, 15, 30, tzinfo=ZoneInfo("Asia/Kolkata")),
    )

    assert cache.required_closed_at == "2026-07-10T15:25:00+05:30"


def test_kwargs_metadata_cache_receives_required_closed_at():
    cache = KwargsMetadataCache()
    client = MagicMock()
    client.get_historical_data.return_value = candle_data()

    service = LiveMultiTimeframeData(client=client, cache=cache)

    service.fetch_timeframe_raw(
        exchange="NSE",
        symboltoken="99926000",
        timeframe="5m",
        end_time=datetime(2026, 7, 10, 15, 30, tzinfo=ZoneInfo("Asia/Kolkata")),
    )

    assert cache.reader_kwargs["required_closed_at"] == "2026-07-10T15:25:00+05:30"


def test_internal_cache_type_error_is_not_retried_as_legacy_api():
    cache = InternalTypeErrorMetadataCache()
    service = LiveMultiTimeframeData(client=MagicMock(), cache=cache)

    with pytest.raises(TypeError, match="cache implementation failure"):
        service.fetch_timeframe_raw(
            exchange="NSE",
            symboltoken="99926000",
            timeframe="5m",
            end_time=datetime(2026, 7, 10, 15, 30, tzinfo=ZoneInfo("Asia/Kolkata")),
        )

    assert cache.calls == 1


def test_live_capture_retains_historical_rate_limit_reason(
    monkeypatch,
):
    from services.broker.market_data_control import (
        BrokerMarketDataRequestError,
    )

    client = MagicMock()
    client.get_historical_data.side_effect = (
        BrokerMarketDataRequestError(
            "historical-data",
            1,
            "rate_limited",
            "sanitized provider failure",
        )
    )

    service = LiveMultiTimeframeData(
        client=client,
        cache=make_cache(),
    )

    monkeypatch.setattr(
        "services.market.live_multi_timeframe_data.TIMEFRAME_CONFIG",
        {
            "5m": {
                "interval": "FIVE_MINUTE",
                "lookback_days": 3,
            }
        },
    )

    result = service.fetch_all_with_capture(
        exchange="NSE",
        symboltoken="99926000",
        end_time=datetime(
            2026,
            7,
            10,
            15,
            30,
        ),
    )

    metadata = result["cache_metadata"]["5m"]

    assert result["rows_by_timeframe"]["5m"] == ()
    assert metadata["captured"] is False
    assert (
        metadata["failure_reason"]
        == "HISTORICAL-DATA_RATE_LIMITED"
    )
    assert metadata["provider_throttled"] is True
