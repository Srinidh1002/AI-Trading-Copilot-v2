"""
Central Market Data Manager

Single source of truth for historical market data.
"""

from datetime import datetime, timedelta
from threading import Lock

from services.historical_data_cache import (
    HistoricalDataCache,
)

from services.data_normalizer import (
    normalize_angel_candles,
)

from services.market.live_multi_timeframe_data import (
    LiveMultiTimeframeData,
)


REFRESH_INTERVAL = {
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}


DISK_CACHE_SECONDS = {
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "1d": 86400,
}


class MarketDataManager:

    def __init__(self):

        self.service = LiveMultiTimeframeData()

        self.cache = HistoricalDataCache()

        self._frames = {}

        self._timestamps = {}

        self._lock = Lock()

        self.stats = {
            "memory_hits": 0,
            "disk_hits": 0,
            "api_calls": 0,
            "cache_misses": 0,
        }

    # ---------------------------------------------------------

    def _expired(
        self,
        key,
        timeframe,
    ):

        if key not in self._timestamps:
            return True

        refresh_after = REFRESH_INTERVAL.get(
            timeframe,
            timedelta(minutes=5),
        )

        return (
            datetime.now()
            - self._timestamps[key]
        ) >= refresh_after

    # ---------------------------------------------------------

    def _load_from_disk(
        self,
        exchange,
        symboltoken,
        timeframe,
    ):

        response = self.cache.get(
            exchange=exchange,
            symboltoken=symboltoken,
            timeframe=timeframe,
            max_age_seconds=DISK_CACHE_SECONDS[
                timeframe
            ],
        )

        if response is None:
            return None

        self.stats["disk_hits"] += 1

        return normalize_angel_candles(
            response["data"]
        )

    # ---------------------------------------------------------

    def _load_from_broker(
        self,
        exchange,
        symboltoken,
        timeframe,
    ):

        self.stats["api_calls"] += 1

        response = (
            self.service.fetch_timeframe_raw(
                exchange=exchange,
                symboltoken=symboltoken,
                timeframe=timeframe,
            )
        )

        self.cache.set(
            exchange=exchange,
            symboltoken=symboltoken,
            timeframe=timeframe,
            response=response,
        )

        return normalize_angel_candles(
            response["data"]
        )

    # ---------------------------------------------------------

    def get_timeframe(
        self,
        exchange,
        symboltoken,
        timeframe,
        force_refresh=False,
    ):

        key = (
            exchange,
            symboltoken,
            timeframe,
        )

        with self._lock:

            if (
                not force_refresh
                and key in self._frames
                and not self._expired(
                    key,
                    timeframe,
                )
            ):

                self.stats["memory_hits"] += 1

                return self._frames[key]

        if not force_refresh:

            df = self._load_from_disk(
                exchange,
                symboltoken,
                timeframe,
            )

            if df is not None:

                with self._lock:

                    self._frames[key] = df
                    self._timestamps[
                        key
                    ] = datetime.now()

                return df

        self.stats["cache_misses"] += 1

        df = self._load_from_broker(
            exchange,
            symboltoken,
            timeframe,
        )

        with self._lock:

            self._frames[key] = df
            self._timestamps[
                key
            ] = datetime.now()

        return df

    # ---------------------------------------------------------

    def get_multiple(
        self,
        exchange,
        symboltoken,
        timeframes,
        force_refresh=False,
    ):

        return {
            timeframe: self.get_timeframe(
                exchange=exchange,
                symboltoken=symboltoken,
                timeframe=timeframe,
                force_refresh=force_refresh,
            )
            for timeframe in timeframes
        }

    # ---------------------------------------------------------

    def cache_info(
        self,
    ):

        return {
            **self.stats,
            "memory_entries": len(
                self._frames
            ),
        }

    # ---------------------------------------------------------

    def clear_memory_cache(
        self,
    ):

        with self._lock:

            self._frames.clear()
            self._timestamps.clear()


market_data_manager = MarketDataManager()