"""
Live multi-timeframe market-data service.

Fetches historical candles from Angel One and converts them into
standard OHLCV DataFrames.

Read-only. A supplied or default historical-data cache may be used to avoid
repeating fresh broker requests.
"""
import time
import os
from datetime import datetime, timedelta

from services.broker.shared_client import (
    get_market_client,
)

from services.data_normalizer import (
    normalize_angel_candles,
)
from services.historical_data_cache import HistoricalDataCache


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

    The cache dependency is optional for backwards-compatible deterministic
    construction. New callers should prefer explicit dependency injection.
    """

    def __init__(
        self,
        client=None,
        cache=None,
        *,
        cache_enabled=None,
    ):
        self.client = (
            client
            if client is not None
            else get_market_client()
        )
        self.cache = (
            cache
            if cache is not None
            else HistoricalDataCache()
        )

        if cache_enabled is None:
            cache_enabled = (
                str(
                    os.getenv(
                        "HISTORICAL_DATA_CACHE_ENABLED",
                        "true",
                    )
                ).strip().lower()
                in {"1", "true", "yes", "on"}
            )

        self.cache_enabled = bool(cache_enabled)

    @staticmethod
    def _cache_ttl_seconds(timeframe):
        return {
            "5m": 240.0,
            "15m": 600.0,
            "1h": 2700.0,
            "1d": 21600.0,
        }[timeframe]

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

        if self.cache_enabled:
            cached_response = self.cache.get(
                exchange,
                symboltoken,
                timeframe,
                max_age_seconds=self._cache_ttl_seconds(timeframe),
            )
            if cached_response is not None:
                candles = cached_response.get("data", [])
                if candles:
                    return cached_response

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

        if self.cache_enabled:
            self.cache.set(
                exchange,
                symboltoken,
                timeframe,
                response,
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
        results = {}
        timeframes = tuple(TIMEFRAME_CONFIG)

        for index, timeframe in enumerate(timeframes):
            results[timeframe] = self.fetch_timeframe(
                exchange=exchange,
                symboltoken=symboltoken,
                timeframe=timeframe,
                end_time=end_time,
            )

            # Angel One can reject multiple historical-data requests
            # issued almost simultaneously. Cached responses return
            # immediately, while uncached startup requests are paced.
            if index < len(timeframes) - 1:
                time.sleep(1.25)

        return results
