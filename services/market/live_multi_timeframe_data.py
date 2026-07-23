"""
Live multi-timeframe market-data service.

Fetches historical candles from Angel One and converts them into
standard OHLCV DataFrames.

Read-only.
No caching is performed here.
Caching is handled exclusively by MarketDataManager.
"""

from datetime import datetime, timedelta

from services.broker.shared_client import (
    get_market_client,
)

from services.data_normalizer import (
    normalize_angel_candles,
)


TIMEFRAME_CONFIG = {
    "5m": {
        "interval": "FIVE_MINUTE",
        "lookback_days": 3,
    },
    "15m": {
        "interval": "FIFTEEN_MINUTE",
        "lookback_days": 10,
    },
    "1h": {
        "interval": "ONE_HOUR",
        "lookback_days": 45,
    },
    "1d": {
        "interval": "ONE_DAY",
        "lookback_days": 365,
    },
}


class LiveMultiTimeframeData:
    """
    Fetch and normalize historical candles.

    No caching is performed inside this class.
    """

    def __init__(
        self,
        client=None,
    ):
        self.client = (
            client
            if client is not None
            else get_market_client()
        )

    def _request_historical(
        self,
        exchange,
        symboltoken,
        timeframe,
        end_time=None,
    ):
        if timeframe not in TIMEFRAME_CONFIG:
            raise ValueError(
                f"Unsupported timeframe: {timeframe}"
            )

        config = TIMEFRAME_CONFIG[
            timeframe
        ]

        if end_time is None:
            end_time = datetime.now()

        start_time = end_time - timedelta(
            days=config["lookback_days"]
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

        return response

    def fetch_timeframe_raw(
        self,
        exchange,
        symboltoken,
        timeframe,
        end_time=None,
    ):
        return self._request_historical(
            exchange=exchange,
            symboltoken=symboltoken,
            timeframe=timeframe,
            end_time=end_time,
        )

    def fetch_timeframe(
        self,
        exchange,
        symboltoken,
        timeframe,
        end_time=None,
    ):
        response = self._request_historical(
            exchange=exchange,
            symboltoken=symboltoken,
            timeframe=timeframe,
            end_time=end_time,
        )

        return normalize_angel_candles(
            response["data"]
        )

    def fetch_all(
        self,
        exchange,
        symboltoken,
        end_time=None,
    ):
        return {
            timeframe: self.fetch_timeframe(
                exchange=exchange,
                symboltoken=symboltoken,
                timeframe=timeframe,
                end_time=end_time,
            )
            for timeframe in TIMEFRAME_CONFIG
        }