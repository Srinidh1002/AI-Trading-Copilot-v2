from datetime import datetime
from unittest.mock import MagicMock

import pytest

from services.completed_candle_service import (
    CompletedCandleService,
)

from services.market_data_validator import (
    MarketDataValidationError,
)


def make_service(
    rows,
):
    """
    Create a completed-candle service
    using mocked Angel One candle data.
    """

    client = MagicMock()

    client.get_historical_data.return_value = {
        "status": True,
        "data": rows,
    }

    return CompletedCandleService(
        market_client=client
    )


def test_invalid_ohlc_candle_is_rejected():

    service = make_service(
        [
            [
                "2026-07-10T10:00:00+05:30",
                100,
                90,
                95,
                98,
                1000,
            ],
        ]
    )

    with pytest.raises(
        MarketDataValidationError,
        match="failed integrity validation",
    ):
        service.get_latest_completed_candle(
            exchange="NSE",
            symboltoken="99926000",
            interval="FIVE_MINUTE",
            now=datetime(
                2026,
                7,
                10,
                10,
                10,
            ),
        )


def test_negative_volume_is_rejected():

    service = make_service(
        [
            [
                "2026-07-10T10:00:00+05:30",
                100,
                105,
                95,
                102,
                -100,
            ],
        ]
    )

    with pytest.raises(
        MarketDataValidationError,
        match="failed integrity validation",
    ):
        service.get_latest_completed_candle(
            exchange="NSE",
            symboltoken="99926000",
            interval="FIVE_MINUTE",
            now=datetime(
                2026,
                7,
                10,
                10,
                10,
            ),
        )


def test_zero_price_is_rejected():

    service = make_service(
        [
            [
                "2026-07-10T10:00:00+05:30",
                0,
                105,
                95,
                102,
                1000,
            ],
        ]
    )

    with pytest.raises(
        MarketDataValidationError,
        match="failed integrity validation",
    ):
        service.get_latest_completed_candle(
            exchange="NSE",
            symboltoken="99926000",
            interval="FIVE_MINUTE",
            now=datetime(
                2026,
                7,
                10,
                10,
                10,
            ),
        )


def test_invalid_numeric_price_is_rejected():

    service = make_service(
        [
            [
                "2026-07-10T10:00:00+05:30",
                "INVALID",
                105,
                95,
                102,
                1000,
            ],
        ]
    )

    with pytest.raises(
        MarketDataValidationError,
        match="failed integrity validation",
    ):
        service.get_latest_completed_candle(
            exchange="NSE",
            symboltoken="99926000",
            interval="FIVE_MINUTE",
            now=datetime(
                2026,
                7,
                10,
                10,
                10,
            ),
        )


def test_malformed_row_is_rejected():

    service = make_service(
        [
            [
                "2026-07-10T10:00:00+05:30",
                100,
                105,
            ],
        ]
    )

    with pytest.raises(
        MarketDataValidationError,
        match="failed integrity validation",
    ):
        service.get_latest_completed_candle(
            exchange="NSE",
            symboltoken="99926000",
            interval="FIVE_MINUTE",
            now=datetime(
                2026,
                7,
                10,
                10,
                10,
            ),
        )


def test_invalid_timestamp_is_rejected():

    service = make_service(
        [
            [
                "not-a-valid-timestamp",
                100,
                105,
                95,
                102,
                1000,
            ],
        ]
    )

    with pytest.raises(
        MarketDataValidationError,
        match="failed integrity validation",
    ):
        service.get_latest_completed_candle(
            exchange="NSE",
            symboltoken="99926000",
            interval="FIVE_MINUTE",
            now=datetime(
                2026,
                7,
                10,
                10,
                10,
            ),
        )


def test_corrupted_candle_is_skipped_when_valid_candle_exists():

    service = make_service(
        [
            [
                "2026-07-10T10:00:00+05:30",
                100,
                105,
                95,
                102,
                1000,
            ],
            [
                "2026-07-10T10:05:00+05:30",
                105,
                100,
                95,
                102,
                1000,
            ],
        ]
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
                10,
                10,
                15,
            ),
        )
    )

    assert (
        result["timestamp"]
        == "2026-07-10T10:00:00+05:30"
    )

    assert result["close"] == 102.0


def test_latest_valid_completed_candle_is_selected():

    service = make_service(
        [
            [
                "2026-07-10T10:00:00+05:30",
                100,
                105,
                95,
                102,
                1000,
            ],
            [
                "2026-07-10T10:05:00+05:30",
                102,
                108,
                101,
                107,
                1200,
            ],
            [
                "2026-07-10T10:10:00+05:30",
                107,
                110,
                106,
                109,
                1500,
            ],
        ]
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
                10,
                10,
                12,
            ),
        )
    )

    assert (
        result["timestamp"]
        == "2026-07-10T10:05:00+05:30"
    )

    assert result["close"] == 107.0


def test_forming_candle_is_never_returned():

    service = make_service(
        [
            [
                "2026-07-10T10:05:00+05:30",
                100,
                105,
                95,
                102,
                1000,
            ],
            [
                "2026-07-10T10:10:00+05:30",
                102,
                108,
                101,
                107,
                1200,
            ],
        ]
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
                10,
                10,
                12,
            ),
        )
    )

    assert (
        result["timestamp"]
        == "2026-07-10T10:05:00+05:30"
    )


def test_all_corrupted_candles_fail_closed():

    service = make_service(
        [
            [
                "2026-07-10T10:00:00+05:30",
                100,
                90,
                95,
                98,
                1000,
            ],
            [
                "2026-07-10T10:05:00+05:30",
                0,
                105,
                95,
                102,
                1000,
            ],
            [
                "2026-07-10T10:10:00+05:30",
                100,
                105,
                95,
                102,
                -100,
            ],
        ]
    )

    with pytest.raises(
        MarketDataValidationError,
        match="failed integrity validation",
    ):
        service.get_latest_completed_candle(
            exchange="NSE",
            symboltoken="99926000",
            interval="FIVE_MINUTE",
            now=datetime(
                2026,
                7,
                10,
                10,
                20,
            ),
        )