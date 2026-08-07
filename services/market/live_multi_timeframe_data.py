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

from services.market_data_failure_evidence import (
    classify_market_data_exception,
)

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
        self._capture_cache_status = {}

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

        capture_key = (
            str(exchange).strip().upper(),
            str(symboltoken).strip(),
            timeframe,
        )

        requested_until = (
            end_time.isoformat()
            if isinstance(end_time, datetime)
            else None
        )

        if self.cache_enabled:
            metadata_reader = getattr(
                type(self.cache),
                "get_with_metadata",
                None,
            )

            if callable(metadata_reader):
                cached_result = (
                    self.cache.get_with_metadata(
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

                if cached_result is not None:
                    cached_response = (
                        cached_result.get(
                            "response"
                        )
                    )

                    cache_metadata = (
                        cached_result.get(
                            "metadata"
                        )
                    )

                    if (
                        isinstance(
                            cached_response,
                            dict,
                        )
                        and isinstance(
                            cache_metadata,
                            dict,
                        )
                        and cached_response.get(
                            "data"
                        )
                    ):
                        self._capture_cache_status[
                            capture_key
                        ] = {
                            **cache_metadata,
                            "cache_status": "HIT",
                            "captured": True,
                            "provider_source": (
                                cache_metadata.get(
                                    "cache_source",
                                    "ANGEL_ONE_HISTORICAL",
                                )
                            ),
                            "requested_until": (
                                requested_until
                            ),
                            "cache_write_status": (
                                "NOT_REQUIRED"
                            ),
                        }

                        return cached_response
            else:
                cached_response = self.cache.get(
                    exchange,
                    symboltoken,
                    timeframe,
                    max_age_seconds=(
                        self._cache_ttl_seconds(
                            timeframe
                        )
                    ),
                )

                if (
                    isinstance(
                        cached_response,
                        dict,
                    )
                    and cached_response.get(
                        "data"
                    )
                ):
                    self._capture_cache_status[
                        capture_key
                    ] = {
                        "cache_status": "HIT",
                        "captured": True,
                        "provider_source": (
                            "HISTORICAL_CACHE"
                        ),
                        "requested_until": (
                            requested_until
                        ),
                        "cache_write_status": (
                            "NOT_REQUIRED"
                        ),
                    }

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

        normalize_angel_candles(
            candles
        )

        cache_write_status = "DISABLED"
        cached_at_epoch_seconds = None

        if self.cache_enabled:
            self.cache.set(
                exchange,
                symboltoken,
                timeframe,
                response,
                source="ANGEL_ONE_HISTORICAL",
            )

            cache_write_status = "WRITTEN"
            cached_at_epoch_seconds = (
                time.time()
            )

        self._capture_cache_status[
            capture_key
        ] = {
            "cache_status": "MISS",
            "captured": True,
            "provider_source": (
                "ANGEL_ONE_HISTORICAL"
            ),
            "requested_until": (
                requested_until
            ),
            "cache_write_status": (
                cache_write_status
            ),
            "cached_at_epoch_seconds": (
                cached_at_epoch_seconds
            ),
            "age_seconds": 0.0,
            "expired": False,
        }

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

    def fetch_all_with_capture(self, exchange, symboltoken, end_time=None):
        """Return existing DataFrames plus the same captured Angel rows."""
        dataframes, rows, metadata = {}, {}, {}
        for index, timeframe in enumerate(TIMEFRAME_CONFIG):
            try:
                response = self._request_historical(exchange, symboltoken, timeframe, end_time=end_time)
                raw = response.get("data", [])
                rows[timeframe] = tuple(tuple(item) for item in raw)
                dataframes[timeframe] = normalize_angel_candles(raw)
                capture_metadata = (
                    self._capture_cache_status.get(
                        (
                            str(exchange).strip().upper(),
                            str(symboltoken).strip(),
                            timeframe,
                        ),
                        {
                            "cache_status": "UNKNOWN",
                            "captured": True,
                            "provider_source": "UNKNOWN",
                            "cache_write_status": "UNKNOWN",
                        },
                    )
                )

                metadata[timeframe] = {
                    **capture_metadata,
                    "captured": True,
                    "requested_until": (
                        end_time.isoformat()
                        if isinstance(
                            end_time,
                            datetime,
                        )
                        else capture_metadata.get(
                            "requested_until"
                        )
                    ),
                }
            except Exception as exc:
                provider_throttled, failure_reason = (
                    classify_market_data_exception(exc)
                )
                rows[timeframe] = ()
                metadata[timeframe] = {
                    "captured": False,
                    "error": type(exc).__name__,
                    "failure_reason": failure_reason,
                    "provider_throttled": provider_throttled,
                }
            if index < len(TIMEFRAME_CONFIG) - 1: time.sleep(1.25)
        return {"dataframes": dataframes, "rows_by_timeframe": rows, "cache_metadata": metadata}
