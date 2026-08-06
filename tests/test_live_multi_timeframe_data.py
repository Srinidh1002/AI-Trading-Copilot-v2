from datetime import datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from services.market.live_multi_timeframe_data import (
    LiveMultiTimeframeData,
)


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
