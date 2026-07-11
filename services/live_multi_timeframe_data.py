"""
Live multi-timeframe market-data service.

Fetches historical candles from Angel One and converts them into
standard OHLCV DataFrames.

This module is read-only and never places orders.
"""

from datetime import datetime, timedelta

from services.broker.angel_client import AngelMarketDataClient
from services.data_normalizer import normalize_angel_candles


TIMEFRAME_CONFIG = {
    "5m": {
        "interval": "FIVE_MINUTE",
        "lookback_days": 10,
    },
    "15m": {
        "interval": "FIFTEEN_MINUTE",
        "lookback_days": 30,
    },
    "1h": {
        "interval": "ONE_HOUR",
        "lookback_days": 120,
    },
    "1d": {
        "interval": "ONE_DAY",
        "lookback_days": 365,
    },
}


class LiveMultiTimeframeData:
    """Fetch and normalize multiple market timeframes."""

    def __init__(self, client=None):
        self.client = (
            client
            if client is not None
            else AngelMarketDataClient()
        )

    def fetch_timeframe(
        self,
        exchange,
        symboltoken,
        timeframe,
        end_time=None,
    ):
        """
        Fetch one timeframe and return a normalized DataFrame.
        """

        if timeframe not in TIMEFRAME_CONFIG:
            raise ValueError(
                f"Unsupported timeframe: {timeframe}"
            )

        config = TIMEFRAME_CONFIG[timeframe]

        if end_time is None:
            end_time = datetime.now()

        start_time = (
            end_time
            - timedelta(
                days=config["lookback_days"]
            )
        )

        response = self.client.get_historical_data(
            exchange=exchange,
            symboltoken=symboltoken,
            interval=config["interval"],
            fromdate=start_time.strftime(
                "%Y-%m-%d %H:%M"
            ),
            todate=end_time.strftime(
                "%Y-%m-%d %H:%M"
            ),
        )

        candles = response.get(
            "data",
            [],
        )

        if not candles:
            raise ValueError(
                f"No candle data returned for {timeframe}."
            )

        return normalize_angel_candles(
            candles
        )

    def fetch_all(
        self,
        exchange,
        symboltoken,
        end_time=None,
    ):
        """
        Fetch all configured timeframes.

        Returns:
        {
            "5m": DataFrame,
            "15m": DataFrame,
            "1h": DataFrame,
            "1d": DataFrame,
        }
        """

        results = {}

        for timeframe in TIMEFRAME_CONFIG:
            results[timeframe] = (
                self.fetch_timeframe(
                    exchange=exchange,
                    symboltoken=symboltoken,
                    timeframe=timeframe,
                    end_time=end_time,
                )
            )

        return results