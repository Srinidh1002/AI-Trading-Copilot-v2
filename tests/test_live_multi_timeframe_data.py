from datetime import datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from services.live_multi_timeframe_data import (
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


def test_fetch_single_timeframe():

    mock_client = MagicMock()

    mock_client.get_historical_data.return_value = (
        candle_data()
    )

    service = LiveMultiTimeframeData(
        client=mock_client
    )

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


def test_fetch_all_timeframes():

    mock_client = MagicMock()

    mock_client.get_historical_data.return_value = (
        candle_data()
    )

    service = LiveMultiTimeframeData(
        client=mock_client
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


def test_invalid_timeframe():

    mock_client = MagicMock()

    service = LiveMultiTimeframeData(
        client=mock_client
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


def test_empty_api_data():

    mock_client = MagicMock()

    mock_client.get_historical_data.return_value = {
        "status": True,
        "data": [],
    }

    service = LiveMultiTimeframeData(
        client=mock_client
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