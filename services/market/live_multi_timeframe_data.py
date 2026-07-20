"""
Live multi-timeframe market-data service.

Fetches historical candles from Angel One and converts them into
standard OHLCV DataFrames.

A persistent timeframe-aware cache reduces unnecessary historical
requests across short-lived opportunity subprocesses.

This module is read-only and never places orders.
"""

import os
from datetime import datetime, timedelta

from services.broker.angel_client import (
    AngelMarketDataClient,
)

from services.data_normalizer import (
    normalize_angel_candles,
)

from services.historical_data_cache import (
    HistoricalDataCache,
)


TIMEFRAME_CONFIG = {
    "5m": {
        "interval": "FIVE_MINUTE",
        "lookback_days": 10,
        "cache_ttl_seconds": 240.0,
    },
    "15m": {
        "interval": "FIFTEEN_MINUTE",
        "lookback_days": 30,
        "cache_ttl_seconds": 600.0,
    },
    "1h": {
        "interval": "ONE_HOUR",
        "lookback_days": 120,
        "cache_ttl_seconds": 2700.0,
    },
    "1d": {
        "interval": "ONE_DAY",
        "lookback_days": 365,
        "cache_ttl_seconds": 21600.0,
    },
}


class LiveMultiTimeframeData:
    """
    Fetch and normalize multiple market timeframes.

    Fresh cached historical responses may be reused across
    separate opportunity subprocesses.
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
            else AngelMarketDataClient()
        )

        self.cache = (
            cache
            if cache is not None
            else HistoricalDataCache()
        )

        if cache_enabled is None:
            raw_value = os.getenv(
                "HISTORICAL_DATA_CACHE_ENABLED",
                "true",
            )

            cache_enabled = (
                str(
                    raw_value
                )
                .strip()
                .lower()
                in {
                    "1",
                    "true",
                    "yes",
                    "on",
                }
            )

        self.cache_enabled = bool(
            cache_enabled
        )

    @staticmethod
    def _cache_ttl_seconds(
        timeframe,
    ):
        return float(
            TIMEFRAME_CONFIG[
                timeframe
            ][
                "cache_ttl_seconds"
            ]
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

        A fresh persistent cache entry is used when available.
        Expired or missing entries trigger a live broker request.
        """

        if timeframe not in TIMEFRAME_CONFIG:
            raise ValueError(
                f"Unsupported timeframe: {timeframe}"
            )

        config = (
            TIMEFRAME_CONFIG[
                timeframe
            ]
        )

        if self.cache_enabled:
            cached_response = (
                self.cache.get(
                    exchange,
                    symboltoken,
                    timeframe,
                    max_age_seconds=(
                        self._cache_ttl_seconds(
                            timeframe
                        )
                    ),
                )
            )

            if cached_response is not None:
                candles = (
                    cached_response.get(
                        "data",
                        [],
                    )
                )

                if candles:
                    return (
                        normalize_angel_candles(
                            candles
                        )
                    )

        if end_time is None:
            end_time = datetime.now()

        start_time = (
            end_time
            - timedelta(
                days=(
                    config[
                        "lookback_days"
                    ]
                )
            )
        )

        response = (
            self.client
            .get_historical_data(
                exchange=exchange,
                symboltoken=symboltoken,
                interval=(
                    config[
                        "interval"
                    ]
                ),
                fromdate=(
                    start_time.strftime(
                        "%Y-%m-%d %H:%M"
                    )
                ),
                todate=(
                    end_time.strftime(
                        "%Y-%m-%d %H:%M"
                    )
                ),
            )
        )

        candles = response.get(
            "data",
            [],
        )

        if not candles:
            raise ValueError(
                f"No candle data returned for {timeframe}."
            )

        normalized = (
            normalize_angel_candles(
                candles
            )
        )

        if self.cache_enabled:
            self.cache.set(
                exchange,
                symboltoken,
                timeframe,
                response,
            )

        return normalized

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
            results[
                timeframe
            ] = (
                self.fetch_timeframe(
                    exchange=exchange,
                    symboltoken=symboltoken,
                    timeframe=timeframe,
                    end_time=end_time,
                )
            )

        return results