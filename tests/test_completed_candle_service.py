from datetime import datetime
from unittest.mock import MagicMock

import pytest
import pandas as pd
from services.completed_candle_service import (
    CompletedCandleService,
)


def test_returns_latest_completed_candle():

    client = MagicMock()

    client.get_historical_data.return_value = {
        "status": True,
        "data": [
            [
                "2026-07-11T10:00:00+05:30",
                100,
                105,
                99,
                104,
                1000,
            ],
            [
                "2026-07-11T10:05:00+05:30",
                104,
                108,
                103,
                107,
                1200,
            ],
            [
                "2026-07-11T10:10:00+05:30",
                107,
                110,
                106,
                109,
                1500,
            ],
        ],
    }

    service = CompletedCandleService(
        market_client=client
    )

    result = (
        service
        .get_latest_completed_candle(
            exchange="NSE",
            symboltoken="99926000",
            interval="FIVE_MINUTE",
            now=datetime(
                2026,
                7,
                11,
                10,
                12,
            ),
        )
    )

    # 10:10 candle is still forming.
    # 10:05 candle completed at 10:10.
    assert (
        result["timestamp"]
        == "2026-07-11T10:05:00+05:30"
    )

    assert result["close"] == 107.0


def test_returns_new_candle_after_completion():

    client = MagicMock()

    client.get_historical_data.return_value = {
        "status": True,
        "data": [
            [
                "2026-07-11T10:05:00+05:30",
                100,
                105,
                99,
                104,
                1000,
            ],
            [
                "2026-07-11T10:10:00+05:30",
                104,
                110,
                103,
                109,
                1500,
            ],
        ],
    }

    service = CompletedCandleService(
        market_client=client
    )

    result = (
        service
        .get_latest_completed_candle(
            exchange="NSE",
            symboltoken="99926000",
            interval="FIVE_MINUTE",
            now=datetime(
                2026,
                7,
                11,
                10,
                15,
            ),
        )
    )

    assert (
        result["timestamp"]
        == "2026-07-11T10:10:00+05:30"
    )

    assert result["close"] == 109.0


def test_raises_when_no_candles_received():

    client = MagicMock()

    client.get_historical_data.return_value = {
        "status": True,
        "data": [],
    }

    service = CompletedCandleService(
        market_client=client
    )

    with pytest.raises(
        RuntimeError,
        match="No candle data received",
    ):
        service.get_latest_completed_candle(
            exchange="NSE",
            symboltoken="99926000",
            now=datetime(
                2026,
                7,
                11,
                10,
                15,
            ),
        )


def test_rejects_unsupported_interval():

    service = CompletedCandleService(
        market_client=MagicMock()
    )

    with pytest.raises(
        ValueError,
        match="Unsupported interval",
    ):
        service.get_latest_completed_candle(
            exchange="NSE",
            symboltoken="99926000",
            interval="INVALID_INTERVAL",
        )
def test_reuses_dataframe_without_broker_request():

    client = MagicMock()

    dataframe = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp(
                    "2026-07-11T10:05:00+05:30"
                ),
                "Open": 100,
                "High": 105,
                "Low": 99,
                "Close": 104,
                "Volume": 1000,
            },
            {
                "timestamp": pd.Timestamp(
                    "2026-07-11T10:10:00+05:30"
                ),
                "Open": 104,
                "High": 110,
                "Low": 103,
                "Close": 109,
                "Volume": 1500,
            },
        ]
    )

    service = CompletedCandleService(
        market_client=client
    )

    result = (
        service
        .get_latest_completed_candle_from_dataframe(
            dataframe=dataframe,
            interval="FIVE_MINUTE",
            now=datetime(
                2026,
                7,
                11,
                10,
                12,
            ),
        )
    )

    assert result["close"] == 104.0

    client.get_historical_data.assert_not_called()        