"""
Live multi-timeframe market-data service.

Fetches historical candles from Angel One and converts them into
standard OHLCV DataFrames.

Read-only. A supplied or default historical-data cache may be used to avoid
repeating fresh broker requests.
"""

from __future__ import annotations

import inspect
import logging
import os
import time as time_module
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from services.broker.angel_endpoint_policies import (
    validate_historical_timeframe_config,
)
from services.broker.market_data_control import (
    BrokerMarketDataRequestError,
)
from services.broker.shared_client import (
    get_market_client,
)
from services.bse_holiday_calendar import (
    get_bse_holiday_calendar,
)
from services.data_normalizer import (
    normalize_angel_candles,
)
from services.historical_data_cache import (
    HistoricalDataCache,
)
from services.historical_provider_cooldown import (
    HistoricalProviderCooldown,
)
from services.historical_request_gate import (
    HistoricalRequestGate,
)
from services.market_data_failure_evidence import (
    classify_market_data_exception,
)
from services.task9_daily_historical_warmup_retry import (
    MAX_ATTEMPTS,
    Task9DailyWarmupRetryStore,
)
from services.nse_holiday_calendar import (
    get_nse_holiday_calendar,
)


logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


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

validate_historical_timeframe_config(
    TIMEFRAME_CONFIG
)


_TIMEFRAME_MINUTES = {
    "5m": 5,
    "15m": 15,
    "1h": 60,
    "1d": 1440,
}


# Historical-data session authority is intentionally separate from
# Task 9 F&O execution-session authority.
#
# Cash/index historical data:
#   NSE / BSE -> 15:30
#
# F&O historical data:
#   NFO / BFO -> 15:40
#
# Task 9's execution policy remains independently responsible for its
# explicitly configured new-entry cutoff and canonical NFO/BFO session close.
_HISTORICAL_REGULAR_OPEN = time(
    9,
    15,
)

_HISTORICAL_REGULAR_CLOSE_BY_EXCHANGE = {
    "NSE": time(
        15,
        30,
    ),
    "BSE": time(
        15,
        30,
    ),
    "NFO": time(
        15,
        40,
    ),
    "BFO": time(
        15,
        40,
    ),
}


def _historical_regular_close(
    exchange,
):
    normalized = str(
        exchange
    ).strip().upper()

    try:
        return (
            _HISTORICAL_REGULAR_CLOSE_BY_EXCHANGE[
                normalized
            ]
        )
    except KeyError as exc:
        raise ValueError(
            "unsupported historical candle exchange"
        ) from exc


def _holiday_calendar_for_exchange(
    exchange,
):
    normalized = str(
        exchange
    ).strip().upper()

    # Validate the exchange first so an unknown
    # segment never silently inherits an incorrect
    # session calendar or close.
    _historical_regular_close(
        normalized
    )

    if normalized in {
        "BSE",
        "BFO",
    }:
        return get_bse_holiday_calendar()

    return get_nse_holiday_calendar()


def _previous_trading_day(
    value,
    exchange,
):
    calendar = (
        _holiday_calendar_for_exchange(
            exchange
        )
    )

    candidate = (
        value.date()
        - timedelta(
            days=1
        )
    )

    while (
        candidate.weekday() > 4
        or calendar.is_holiday(
            candidate
        )
    ):
        candidate -= timedelta(
            days=1
        )

    return candidate


def _last_session_candle_start(
    value,
    timeframe,
    exchange,
):
    previous_day = (
        _previous_trading_day(
            value,
            exchange,
        )
    )

    close = datetime.combine(
        previous_day,
        _historical_regular_close(
            exchange
        ),
        tzinfo=value.tzinfo,
    )

    if timeframe == "1d":
        return close.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

    minutes = {
        "5m": 5,
        "15m": 15,
        "1h": 60,
    }[timeframe]

    minute = (
        close.hour * 60
        + close.minute
    )

    candle_open = (
        minute
        - (minute % minutes)
        - minutes
    )

    return close.replace(
        hour=candle_open // 60,
        minute=candle_open % 60,
        second=0,
        microsecond=0,
    )


def required_closed_candle_at(
    timeframe,
    end_time,
    *,
    exchange="NSE",
):
    """
    Return the latest completed Angel candle start.

    Historical candle close is exchange/segment aware and is deliberately
    independent from Task 9's F&O execution-session policy.
    """

    if (
        end_time.tzinfo is None
        or end_time.utcoffset()
        is None
    ):
        raise ValueError(
            "end_time must be timezone-aware"
        )

    if timeframe not in {
        "5m",
        "15m",
        "1h",
        "1d",
    }:
        raise ValueError(
            f"Unsupported timeframe: {timeframe}"
        )

    value = end_time.astimezone(
        IST
    )

    regular_close = (
        _historical_regular_close(
            exchange
        )
    )

    calendar = (
        _holiday_calendar_for_exchange(
            exchange
        )
    )

    market_time = (
        value.time()
        .replace(
            tzinfo=None
        )
    )

    is_trading_day = (
        value.weekday() < 5
        and not calendar.is_holiday(
            value.date()
        )
    )

    if timeframe == "1d":
        if (
            not is_trading_day
            or market_time
            < regular_close
        ):
            return (
                _last_session_candle_start(
                    value,
                    timeframe,
                    exchange,
                )
            )

        return value.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

    if (
        not is_trading_day
        or market_time
        <= _HISTORICAL_REGULAR_OPEN
    ):
        return (
            _last_session_candle_start(
                value,
                timeframe,
                exchange,
            )
        )

    minutes = {
        "5m": 5,
        "15m": 15,
        "1h": 60,
    }[timeframe]

    effective_time = min(
        market_time,
        regular_close,
    )

    floor = value.replace(
        hour=effective_time.hour,
        minute=effective_time.minute,
        second=0,
        microsecond=0,
    )

    minute = (
        floor.hour * 60
        + floor.minute
    )

    candle_open = (
        minute
        - (minute % minutes)
        - minutes
    )

    return floor.replace(
        hour=candle_open // 60,
        minute=candle_open % 60,
    )


def task9_required_completed_daily_candle_at(end_time, *, exchange="NSE"):
    """Task 9 admits only a completed *prior* trading session for 1D."""
    if end_time.tzinfo is None or end_time.utcoffset() is None:
        raise ValueError("end_time must be timezone-aware")
    return _last_session_candle_start(end_time.astimezone(IST), "1d", exchange)


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
        provider_cooldown=None,
        historical_request_gate=None,
        task9_daily_warmup_retry_store=None,
        *,
        cache_enabled=None,
        historical_request_interval_seconds=None,
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

        cache_path = getattr(
            self.cache,
            "file_path",
            None,
        )
        # A permissive mock (or malformed cache adapter) can manufacture a
        # ``file_path`` attribute.  Never coerce that object into a relative
        # filesystem path for control-state persistence.
        if not isinstance(cache_path, (str, Path)):
            cache_path = None

        if provider_cooldown is None:
            provider_cooldown = (
                HistoricalProviderCooldown(
                    Path(
                        cache_path
                    ).with_name(
                        "angel_historical_provider_cooldown.json"
                    )
                )
                if cache_path is not None
                else None
            )

        if (
            provider_cooldown is not None
            and not callable(
                getattr(
                    provider_cooldown,
                    "active",
                    None,
                )
            )
        ):
            raise TypeError(
                "provider_cooldown"
            )

        self.provider_cooldown = (
            provider_cooldown
        )
        self.task9_daily_warmup_retry_store = (
            task9_daily_warmup_retry_store
            if task9_daily_warmup_retry_store is not None
            else (
                Task9DailyWarmupRetryStore(
                    Path(cache_path).with_name("task9_daily_historical_warmup_retry.json")
                )
                if cache_path is not None
                else None
            )
        )

        if (
            historical_request_interval_seconds
            is not None
        ):
            try:
                historical_request_interval_seconds = float(
                    historical_request_interval_seconds
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                raise ValueError(
                    "historical_request_interval_seconds"
                ) from exc

            if (
                historical_request_interval_seconds
                <= 0
            ):
                raise ValueError(
                    "historical_request_interval_seconds"
                )

        if (
            historical_request_gate
            is None
            and cache_path
            is not None
        ):
            historical_request_gate = (
                HistoricalRequestGate(
                    Path(
                        cache_path
                    ).with_name(
                        "angel_historical_request_gate.json"
                    ),
                    interval_seconds=(
                        1.0
                        if (
                            historical_request_interval_seconds
                            is None
                        )
                        else historical_request_interval_seconds
                    ),
                )
            )

        if (
            historical_request_gate
            is not None
            and not callable(
                getattr(
                    historical_request_gate,
                    "acquire",
                    None,
                )
            )
        ):
            raise TypeError(
                "historical_request_gate"
            )

        self.historical_request_gate = (
            historical_request_gate
        )

        self._capture_cache_status = {}
        self._request_diagnostics = {}

    @staticmethod
    def _cache_ttl_seconds(
        timeframe,
    ):
        return {
            "5m": 240.0,
            "15m": 600.0,
            "1h": 2700.0,
            "1d": 21600.0,
        }[timeframe]

    @staticmethod
    def _cache_supports_required_closed_at(
        cache_reader,
    ):
        """
        Return whether a cache reader explicitly accepts closed coverage.
        """

        try:
            signature = (
                inspect.signature(
                    cache_reader
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            return False

        parameters = (
            signature.parameters
        )

        closed_at_parameter = (
            parameters.get(
                "required_closed_at"
            )
        )

        if (
            closed_at_parameter
            is not None
            and closed_at_parameter.kind
            in {
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            }
        ):
            return True

        return any(
            parameter.kind
            is inspect.Parameter.VAR_KEYWORD
            for parameter
            in parameters.values()
        )

    def _read_cache(
        self,
        method_name,
        exchange,
        symboltoken,
        timeframe,
        *,
        max_age_seconds,
        required_until,
        required_closed_at,
    ):
        """
        Read a cache without imposing new keywords on legacy injections.
        """

        cache_reader = getattr(
            self.cache,
            method_name,
        )

        kwargs = {
            "max_age_seconds": (
                max_age_seconds
            ),
            "required_until": (
                required_until
            ),
        }

        if (
            required_closed_at
            is not None
            and self._cache_supports_required_closed_at(
                cache_reader
            )
        ):
            kwargs[
                "required_closed_at"
            ] = required_closed_at

        return cache_reader(
            exchange,
            symboltoken,
            timeframe,
            **kwargs,
        )

    @staticmethod
    def _normalized_rows(
        response,
    ):
        normalized = (
            normalize_angel_candles(
                response.get(
                    "data"
                )
            )
        )

        return (
            normalized,
            [
                list(
                    row
                )
                for row
                in response[
                    "data"
                ]
            ],
        )

    @staticmethod
    def _first_required_history_timestamp(
        start_time,
        exchange,
    ):
        """
        Earliest plausible provider candle start for the requested range.

        Historical-data session authority is used here instead of the
        independent Task 9 F&O execution policy.
        """

        calendar = (
            _holiday_calendar_for_exchange(
                exchange
            )
        )

        candidate = (
            start_time.astimezone(
                IST
            )
        )

        while (
            candidate.weekday() > 4
            or calendar.is_holiday(
                candidate.date()
            )
        ):
            candidate = (
                candidate
                + timedelta(
                    days=1
                )
            ).replace(
                hour=(
                    _HISTORICAL_REGULAR_OPEN
                    .hour
                ),
                minute=(
                    _HISTORICAL_REGULAR_OPEN
                    .minute
                ),
                second=0,
                microsecond=0,
            )

        return candidate

    def _incremental_refresh_candidate(
        self,
        exchange,
        symboltoken,
        timeframe,
        *,
        start_time,
        required_closed_at,
    ):
        reader = getattr(
            type(
                self.cache
            ),
            "get_incremental_candidate",
            None,
        )

        if (
            not callable(
                reader
            )
            or required_closed_at
            is None
        ):
            return None

        candidate = (
            self.cache
            .get_incremental_candidate(
                exchange,
                symboltoken,
                timeframe,
            )
        )

        if (
            not isinstance(
                candidate,
                dict,
            )
            or not isinstance(
                candidate.get(
                    "response"
                ),
                dict,
            )
        ):
            return None

        try:
            normalized, _ = (
                self._normalized_rows(
                    candidate[
                        "response"
                    ]
                )
            )

            first = (
                normalized[
                    "timestamp"
                ]
                .iloc[
                    0
                ]
                .to_pydatetime()
            )

            latest = (
                normalized[
                    "timestamp"
                ]
                .iloc[
                    -1
                ]
                .to_pydatetime()
            )

            required_closed = (
                datetime.fromisoformat(
                    required_closed_at
                )
            )

        except (
            AttributeError,
            IndexError,
            TypeError,
            ValueError,
        ):
            return None

        if first > (
            self._first_required_history_timestamp(
                start_time,
                exchange,
            )
        ):
            return None

        if latest >= required_closed:
            return None

        return candidate

    def _merge_incremental_response(
        self,
        cached_response,
        tail_response,
        *,
        required_closed_at,
    ):
        (
            cached_normalized,
            cached_rows,
        ) = self._normalized_rows(
            cached_response
        )

        (
            tail_normalized,
            tail_rows,
        ) = self._normalized_rows(
            tail_response
        )

        merged = {}

        for (
            timestamp,
            row,
        ) in zip(
            cached_normalized[
                "timestamp"
            ],
            cached_rows,
        ):
            merged[
                timestamp
            ] = row

        for (
            timestamp,
            row,
        ) in zip(
            tail_normalized[
                "timestamp"
            ],
            tail_rows,
        ):
            merged[
                timestamp
            ] = row

        merged_rows = [
            row
            for _, row
            in sorted(
                merged.items(),
                key=lambda value: (
                    value[
                        0
                    ]
                ),
            )
        ]

        merged_response = {
            **cached_response,
            **tail_response,
            "data": (
                merged_rows
            ),
        }

        (
            merged_normalized,
            _,
        ) = self._normalized_rows(
            merged_response
        )

        required_closed = (
            datetime.fromisoformat(
                required_closed_at
            )
        )

        timestamps = set(
            merged_normalized[
                "timestamp"
            ]
        )

        if (
            required_closed
            not in timestamps
        ):
            raise ValueError(
                "Incremental response does not "
                "cover required closed candle."
            )

        if (
            len(
                merged_normalized
            )
            < len(
                cached_normalized
            )
        ):
            raise ValueError(
                "Incremental response truncated "
                "cached history."
            )

        return merged_response

    @staticmethod
    def _new_request_diagnostic(
        exchange,
        symboltoken,
        timeframe,
        required_closed_at,
    ):
        return {
            "exchange": (
                str(
                    exchange
                )
                .strip()
                .upper()
            ),
            "symboltoken": (
                str(
                    symboltoken
                )
                .strip()
            ),
            "timeframe": (
                timeframe
            ),
            "required_closed_at": (
                required_closed_at
            ),
            "latest_cached_candle_at": (
                None
            ),
            "cache_decision": (
                "MISS"
            ),
            "refresh_mode": (
                "FULL"
            ),
            "request_from": (
                None
            ),
            "request_to": (
                None
            ),
            "gate_acquired": (
                False
            ),
            "provider_attempted": (
                False
            ),
            "provider_result": (
                "NOT_ATTEMPTED"
            ),
            "merge_result": (
                "NOT_REQUIRED"
            ),
            "cache_write_result": (
                "NOT_ATTEMPTED"
            ),
            "failure_reason": (
                None
            ),
        }

    def _record_request_diagnostic(
        self,
        capture_key,
        diagnostic,
    ):
        self._request_diagnostics[
            capture_key
        ] = dict(
            diagnostic
        )

    @staticmethod
    def _latest_cached_candle_at(
        response,
    ):
        try:
            normalized, _ = (
                LiveMultiTimeframeData
                ._normalized_rows(
                    response
                )
            )

            return (
                normalized[
                    "timestamp"
                ]
                .iloc[
                    -1
                ]
                .isoformat()
            )

        except (
            AttributeError,
            IndexError,
            TypeError,
            ValueError,
        ):
            return None

    def _request_historical(
        self,
        exchange,
        symboltoken,
        timeframe,
        end_time=None,
        minimum_completed_candles=None,
    ):
        if (
            timeframe
            not in TIMEFRAME_CONFIG
        ):
            raise ValueError(
                f"Unsupported timeframe: "
                f"{timeframe}"
            )

        config = (
            TIMEFRAME_CONFIG[
                timeframe
            ]
        )

        if minimum_completed_candles is not None:
            if (
                timeframe != "1d"
                or type(minimum_completed_candles) is not int
                or minimum_completed_candles <= 0
            ):
                raise ValueError(
                    "minimum_completed_candles"
                )

        if end_time is None:
            end_time = (
                datetime.now(
                    IST
                )
            )

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

        capture_key = (
            str(
                exchange
            ).strip().upper(),
            str(
                symboltoken
            ).strip(),
            timeframe,
        )

        requested_until = (
            end_time.isoformat()
            if isinstance(
                end_time,
                datetime,
            )
            else None
        )

        cache_ttl_seconds = (
            self._cache_ttl_seconds(
                timeframe
            )
        )

        required_until = None
        required_closed_at = None

        if isinstance(
            end_time,
            datetime,
        ):
            required_until = (
                end_time
                - timedelta(
                    seconds=(
                        cache_ttl_seconds
                    )
                )
            ).isoformat()

            if (
                end_time.tzinfo
                is not None
                and end_time.utcoffset()
                is not None
            ):
                required_closed_at = (
                    required_closed_candle_at(
                        timeframe,
                        end_time,
                        exchange=exchange,
                    )
                    .isoformat()
                )

        diagnostic = (
            self._new_request_diagnostic(
                exchange,
                symboltoken,
                timeframe,
                required_closed_at,
            )
        )

        if self.cache_enabled:
            metadata_reader = getattr(
                type(
                    self.cache
                ),
                "get_with_metadata",
                None,
            )

            if callable(
                metadata_reader
            ):
                cached_result = (
                    self._read_cache(
                        "get_with_metadata",
                        exchange,
                        symboltoken,
                        timeframe,
                        max_age_seconds=(
                            cache_ttl_seconds
                        ),
                        required_until=(
                            required_until
                        ),
                        required_closed_at=(
                            required_closed_at
                        ),
                    )
                )

                if (
                    cached_result
                    is not None
                ):
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
                        and (
                            minimum_completed_candles is None
                            or self._has_required_daily_coverage(
                                cached_response,
                                required_closed_at,
                                minimum_completed_candles,
                            )
                        )
                    ):
                        diagnostic.update(
                            latest_cached_candle_at=(
                                self._latest_cached_candle_at(
                                    cached_response
                                )
                            ),
                            cache_decision=(
                                "HIT"
                            ),
                            refresh_mode=(
                                "NONE"
                            ),
                            cache_write_result=(
                                "NOT_REQUIRED"
                            ),
                        )

                        self._record_request_diagnostic(
                            capture_key,
                            diagnostic,
                        )

                        self._capture_cache_status[
                            capture_key
                        ] = {
                            **cache_metadata,
                            "cache_status": (
                                "HIT"
                            ),
                            "captured": (
                                True
                            ),
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

                        return (
                            cached_response
                        )

            else:
                cached_response = (
                    self._read_cache(
                        "get",
                        exchange,
                        symboltoken,
                        timeframe,
                        max_age_seconds=(
                            cache_ttl_seconds
                        ),
                        required_until=(
                            required_until
                        ),
                        required_closed_at=(
                            required_closed_at
                        ),
                    )
                )

                if (
                    isinstance(
                        cached_response,
                        dict,
                    )
                    and cached_response.get(
                        "data"
                    )
                    and (
                        minimum_completed_candles is None
                        or self._has_required_daily_coverage(
                            cached_response,
                            required_closed_at,
                            minimum_completed_candles,
                        )
                    )
                ):
                    diagnostic.update(
                        latest_cached_candle_at=(
                            self._latest_cached_candle_at(
                                cached_response
                            )
                        ),
                        cache_decision=(
                            "HIT"
                        ),
                        refresh_mode=(
                            "NONE"
                        ),
                        cache_write_result=(
                            "NOT_REQUIRED"
                        ),
                    )

                    self._record_request_diagnostic(
                        capture_key,
                        diagnostic,
                    )

                    self._capture_cache_status[
                        capture_key
                    ] = {
                        "cache_status": (
                            "HIT"
                        ),
                        "captured": (
                            True
                        ),
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

                    return (
                        cached_response
                    )

        incremental_candidate = (
            self._incremental_refresh_candidate(
                exchange,
                symboltoken,
                timeframe,
                start_time=(
                    start_time
                ),
                required_closed_at=(
                    required_closed_at
                ),
            )
        )

        request_start_time = (
            start_time
        )

        if (
            incremental_candidate
            is not None
        ):
            latest_cached = (
                datetime.fromisoformat(
                    incremental_candidate[
                        "metadata"
                    ][
                        "latest_candle_start"
                    ]
                )
            )

            request_start_time = (
                latest_cached
                - timedelta(
                    minutes=(
                        _TIMEFRAME_MINUTES[
                            timeframe
                        ]
                    )
                )
            )

            diagnostic.update(
                latest_cached_candle_at=(
                    latest_cached
                    .isoformat()
                ),
                cache_decision=(
                    "INSUFFICIENT_CLOSED_CANDLE"
                ),
                refresh_mode=(
                    "INCREMENTAL"
                ),
                merge_result=(
                    "NOT_ATTEMPTED"
                ),
            )

        diagnostic[
            "request_from"
        ] = (
            request_start_time.strftime(
                "%Y-%m-%d %H:%M"
            )
        )

        diagnostic[
            "request_to"
        ] = (
            end_time.strftime(
                "%Y-%m-%d %H:%M"
            )
        )

        cooldown = (
            self.provider_cooldown.active()
            if (
                self.provider_cooldown
                is not None
            )
            else None
        )

        if cooldown is not None:
            diagnostic[
                "failure_reason"
            ] = (
                "HISTORICAL-DATA_RATE_LIMITED"
            )

            self._record_request_diagnostic(
                capture_key,
                diagnostic,
            )

            raise (
                BrokerMarketDataRequestError(
                    "historical-data",
                    0,
                    "rate_limited",
                    (
                        "persisted "
                        "historical cooldown"
                    ),
                )
            )

        gate_result = (
            self.historical_request_gate
            .acquire()
            if (
                self.historical_request_gate
                is not None
            )
            else None
        )

        diagnostic[
            "gate_acquired"
        ] = (
            self.historical_request_gate
            is not None
        )

        logger.info(
            (
                "historical_provider_request "
                "exchange=%s "
                "symboltoken=%s "
                "timeframe=%s "
                "mode=%s "
                "fromdate=%s "
                "todate=%s "
                "required_closed_at=%s"
            ),
            diagnostic[
                "exchange"
            ],
            diagnostic[
                "symboltoken"
            ],
            diagnostic[
                "timeframe"
            ],
            diagnostic[
                "refresh_mode"
            ],
            diagnostic[
                "request_from"
            ],
            diagnostic[
                "request_to"
            ],
            diagnostic[
                "required_closed_at"
            ],
        )

        diagnostic[
            "provider_attempted"
        ] = True

        # Persist the outbound-attempt fact before calling the provider.
        # Later response validation, normalization, merging, or cache-write
        # failures must still consume the bounded warm-up attempt.
        self._record_request_diagnostic(
            capture_key,
            diagnostic,
        )

        try:
            response = (
                self.client
                .get_historical_data(
                    exchange=exchange,
                    symboltoken=(
                        symboltoken
                    ),
                    interval=(
                        config[
                            "interval"
                        ]
                    ),
                    fromdate=(
                        request_start_time
                        .strftime(
                            "%Y-%m-%d %H:%M"
                        )
                    ),
                    todate=(
                        end_time
                        .strftime(
                            "%Y-%m-%d %H:%M"
                        )
                    ),
                )
            )

        except Exception as exc:
            (
                provider_throttled,
                failure_reason,
            ) = (
                classify_market_data_exception(
                    exc
                )
            )

            diagnostic.update(
                provider_result=(
                    "RATE_LIMITED"
                    if provider_throttled
                    else "FAILED"
                ),
                failure_reason=(
                    failure_reason
                ),
            )

            self._record_request_diagnostic(
                capture_key,
                diagnostic,
            )

            logger.info(
                (
                    "historical_provider_result "
                    "exchange=%s "
                    "symboltoken=%s "
                    "timeframe=%s "
                    "mode=%s "
                    "result=%s "
                    "failure_reason=%s"
                ),
                diagnostic[
                    "exchange"
                ],
                diagnostic[
                    "symboltoken"
                ],
                diagnostic[
                    "timeframe"
                ],
                diagnostic[
                    "refresh_mode"
                ],
                diagnostic[
                    "provider_result"
                ],
                diagnostic[
                    "failure_reason"
                ],
            )

            if (
                provider_throttled
                and self.provider_cooldown
                is not None
            ):
                controller = getattr(
                    self.client,
                    "request_controller",
                    None,
                )

                duration = getattr(
                    controller,
                    "rate_limit_cooldown_seconds",
                    0.0,
                )

                self.provider_cooldown.record_rate_limit(
                    reason=(
                        failure_reason
                    ),
                    cooldown_seconds=(
                        duration
                    ),
                )

            raise

        diagnostic[
            "provider_result"
        ] = "SUCCESS"

        candles = response.get(
            "data",
            [],
        )

        if not candles:
            diagnostic.update(
                provider_result=(
                    "FAILED"
                ),
                failure_reason=(
                    "HISTORICAL-DATA_EMPTY_DATA"
                ),
            )

            self._record_request_diagnostic(
                capture_key,
                diagnostic,
            )

            raise ValueError(
                f"No candle data returned "
                f"for {timeframe}."
            )

        normalize_angel_candles(
            candles
        )

        if (
            incremental_candidate
            is not None
        ):
            response = (
                self._merge_incremental_response(
                    incremental_candidate[
                        "response"
                    ],
                    response,
                    required_closed_at=(
                        required_closed_at
                    ),
                )
            )

            diagnostic[
                "merge_result"
            ] = "SUCCESS"

        if (
            minimum_completed_candles is not None
            and not self._has_required_daily_coverage(
                response,
                required_closed_at,
                minimum_completed_candles,
            )
        ):
            diagnostic.update(
                provider_result=(
                    "FAILED"
                ),
                failure_reason=(
                    "HISTORICAL-DATA_INSUFFICIENT_COMPLETED_DAILY_CANDLES"
                ),
            )
            self._record_request_diagnostic(
                capture_key,
                diagnostic,
            )
            raise ValueError(
                "Insufficient completed daily candle coverage."
            )

        cache_write_status = (
            "DISABLED"
        )

        cached_at_epoch_seconds = (
            None
        )

        if self.cache_enabled:
            self.cache.set(
                exchange,
                symboltoken,
                timeframe,
                response,
                source=(
                    "ANGEL_ONE_HISTORICAL"
                ),
                requested_until=(
                    requested_until
                ),
            )

            cache_write_status = (
                "WRITTEN"
            )

            cached_at_epoch_seconds = (
                time_module.time()
            )

            diagnostic[
                "cache_write_result"
            ] = "SUCCESS"

        self._record_request_diagnostic(
            capture_key,
            diagnostic,
        )

        logger.info(
            (
                "historical_provider_result "
                "exchange=%s "
                "symboltoken=%s "
                "timeframe=%s "
                "mode=%s "
                "result=%s "
                "merge_result=%s "
                "cache_write_result=%s"
            ),
            diagnostic[
                "exchange"
            ],
            diagnostic[
                "symboltoken"
            ],
            diagnostic[
                "timeframe"
            ],
            diagnostic[
                "refresh_mode"
            ],
            diagnostic[
                "provider_result"
            ],
            diagnostic[
                "merge_result"
            ],
            diagnostic[
                "cache_write_result"
            ],
        )

        self._capture_cache_status[
            capture_key
        ] = {
            "cache_status": (
                "MISS"
            ),
            "captured": (
                True
            ),
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
            "age_seconds": (
                0.0
            ),
            "expired": (
                False
            ),
            "cross_process_gate_wait_seconds": (
                gate_result.get(
                    "wait_seconds",
                    0.0,
                )
                if isinstance(
                    gate_result,
                    dict,
                )
                else 0.0
            ),
        }

        return response

    @staticmethod
    def _has_required_daily_coverage(
        response,
        required_closed_at,
        minimum_completed_candles,
    ):
        """Require an exact completed daily identity and sufficient history."""

        if (
            not isinstance(response, dict)
            or required_closed_at is None
            or type(minimum_completed_candles) is not int
            or minimum_completed_candles <= 0
        ):
            return False

        try:
            required = datetime.fromisoformat(
                required_closed_at
            )
            normalized, _ = (
                LiveMultiTimeframeData._normalized_rows(
                    response
                )
            )
            timestamps = tuple(
                item.to_pydatetime()
                for item in normalized["timestamp"]
            )
        except (
            AttributeError,
            KeyError,
            TypeError,
            ValueError,
        ):
            return False

        completed = tuple(
            item
            for item in timestamps
            if item <= required
        )
        return (
            required in completed
            and len(completed) >= minimum_completed_candles
        )

    def ensure_daily_cache_coverage(
        self,
        exchange,
        symboltoken,
        *,
        end_time,
        minimum_completed_candles=50,
    ):
        """Ensure one truthful, completed 1D cache authority for a cycle date.

        The ordinary persistent-cache and historical-request controls remain
        authoritative.  A valid durable cache is reused across restart; a
        failed optional refresh is reported rather than manufactured.
        """

        required_closed_at = task9_required_completed_daily_candle_at(
            end_time,
            exchange=exchange,
        ).isoformat()
        capture_key = (
            str(exchange).strip().upper(),
            str(symboltoken).strip(),
            "1d",
        )

        retry_store = self.task9_daily_warmup_retry_store
        try:
            retry = (
                retry_store.status(
                    exchange=capture_key[0], symboltoken=capture_key[1],
                    required_identity=required_closed_at,
                )
                if retry_store is not None else None
            )
            now_epoch = float(retry_store.time_function()) if retry_store is not None else None
            if retry is not None and (
                retry["attempt_count"] >= MAX_ATTEMPTS
                or (retry["next_attempt_at_epoch_seconds"] is not None and now_epoch < retry["next_attempt_at_epoch_seconds"])
            ):
                return {
                    "exchange": capture_key[0], "symboltoken": capture_key[1], "interval": "ONE_DAY",
                    "required_completed_candle_at": required_closed_at, "cache_state_before": "STALE_OR_MISSING",
                    "refresh_attempted": False,
                    "refresh_outcome": "ATTEMPT_BUDGET_EXHAUSTED" if retry["attempt_count"] >= MAX_ATTEMPTS else "RETRY_BACKOFF_ACTIVE",
                    "cache_state_after": "UNAVAILABLE", "row_count": 0,
                    "latest_completed_candle_at": None, "provider_call_count": 0, "logical_attempt_count": retry["attempt_count"],
                    "next_attempt_at_epoch_seconds": retry["next_attempt_at_epoch_seconds"], "blockers": (),
                    "warnings": ("OPTIONAL_TIMEFRAME_UNAVAILABLE_1D",),
                }
            response = self._request_historical(
                exchange=exchange,
                symboltoken=symboltoken,
                timeframe="1d",
                end_time=end_time,
                minimum_completed_candles=minimum_completed_candles,
            )
            diagnostic = dict(
                self._request_diagnostics.get(
                    capture_key,
                    {},
                )
            )
            provider_attempted = bool(
                diagnostic.get("provider_attempted")
            )
            # Daily coverage has already proven the exact required
            # completed-session identity. Provider rows after that identity
            # may be retained as partial/future observations, but must not
            # be reported as completed.
            latest = required_closed_at
            result = {
                "exchange": capture_key[0],
                "symboltoken": capture_key[1],
                "interval": "ONE_DAY",
                "required_completed_candle_at": required_closed_at,
                "cache_state_before": (
                    "FRESH"
                    if diagnostic.get("cache_decision") == "HIT"
                    else "STALE_OR_MISSING"
                ),
                "refresh_attempted": provider_attempted,
                "refresh_outcome": (
                    "REFRESHED" if provider_attempted else "REUSED"
                ),
                "cache_state_after": "READY",
                "row_count": len(response.get("data", ())),
                "latest_completed_candle_at": latest,
                "provider_call_count": int(provider_attempted),
                "logical_attempt_count": 0,
                "next_attempt_at_epoch_seconds": None,
                "blockers": (),
                "warnings": (),
            }
            if retry_store is not None:
                retry_store.clear(exchange=capture_key[0], symboltoken=capture_key[1], required_identity=required_closed_at)
        except Exception as exc:
            diagnostic = dict(
                self._request_diagnostics.get(
                    capture_key,
                    {},
                )
            )
            cooldown = self.provider_cooldown.active() if self.provider_cooldown is not None else None
            provider_attempted = bool(diagnostic.get("provider_attempted"))
            try:
                retry = (
                    retry_store.record_failure(
                    exchange=capture_key[0], symboltoken=capture_key[1], required_identity=required_closed_at,
                    failure_category=diagnostic.get("failure_reason") or type(exc).__name__,
                    not_before_epoch_seconds=(cooldown or {}).get("expires_at_epoch_seconds"),
                    )
                    if retry_store is not None and provider_attempted
                    else retry_store.status(
                    exchange=capture_key[0], symboltoken=capture_key[1], required_identity=required_closed_at,
                    )
                    if retry_store is not None
                    else None
                )
            except ValueError:
                return {
                    "exchange": capture_key[0], "symboltoken": capture_key[1], "interval": "ONE_DAY",
                    "required_completed_candle_at": required_closed_at, "cache_state_before": "RETRY_STATE_INVALID",
                    "refresh_attempted": False, "refresh_outcome": "RETRY_STATE_INVALID",
                    "cache_state_after": "UNAVAILABLE", "row_count": 0, "latest_completed_candle_at": None,
                    "provider_call_count": 0, "logical_attempt_count": 0, "next_attempt_at_epoch_seconds": None,
                    "blockers": (), "warnings": ("OPTIONAL_TIMEFRAME_UNAVAILABLE_1D",),
                }
            result = {
                "exchange": capture_key[0],
                "symboltoken": capture_key[1],
                "interval": "ONE_DAY",
                "required_completed_candle_at": required_closed_at,
                "cache_state_before": "STALE_OR_MISSING",
                "refresh_attempted": bool(
                    diagnostic.get("provider_attempted")
                ),
                "refresh_outcome": "PROVIDER_THROTTLED" if not provider_attempted and cooldown is not None else "UNAVAILABLE",
                "cache_state_after": "UNAVAILABLE",
                "row_count": 0,
                "latest_completed_candle_at": diagnostic.get(
                    "latest_cached_candle_at"
                ),
                "provider_call_count": int(
                    bool(diagnostic.get("provider_attempted"))
                ),
                "logical_attempt_count": retry["attempt_count"] if retry is not None else int(provider_attempted),
                "next_attempt_at_epoch_seconds": retry["next_attempt_at_epoch_seconds"] if retry is not None else None,
                "blockers": (),
                "warnings": (
                    "OPTIONAL_TIMEFRAME_UNAVAILABLE_1D",
                ),
            }

        logger.info(
            "daily_historical_cache_warmup exchange=%s symboltoken=%s "
            "interval=%s required_completed_candle_at=%s "
            "cache_state_before=%s refresh_attempted=%s "
            "refresh_outcome=%s cache_state_after=%s row_count=%s "
            "latest_completed_candle_at=%s provider_call_count=%s",
            result["exchange"],
            result["symboltoken"],
            result["interval"],
            result["required_completed_candle_at"],
            result["cache_state_before"],
            result["refresh_attempted"],
            result["refresh_outcome"],
            result["cache_state_after"],
            result["row_count"],
            result["latest_completed_candle_at"],
            result["provider_call_count"],
        )
        return result

    def fetch_timeframe_raw(
        self,
        exchange,
        symboltoken,
        timeframe,
        end_time=None,
    ):
        return (
            self._request_historical(
                exchange=exchange,
                symboltoken=(
                    symboltoken
                ),
                timeframe=(
                    timeframe
                ),
                end_time=(
                    end_time
                ),
            )
        )

    def fetch_timeframe(
        self,
        exchange,
        symboltoken,
        timeframe,
        end_time=None,
    ):
        response = (
            self._request_historical(
                exchange=exchange,
                symboltoken=(
                    symboltoken
                ),
                timeframe=(
                    timeframe
                ),
                end_time=(
                    end_time
                ),
            )
        )

        return (
            normalize_angel_candles(
                response[
                    "data"
                ]
            )
        )

    def fetch_all(
        self,
        exchange,
        symboltoken,
        end_time=None,
    ):
        results = {}

        timeframes = tuple(
            TIMEFRAME_CONFIG
        )

        for timeframe in timeframes:
            results[
                timeframe
            ] = (
                self.fetch_timeframe(
                    exchange=exchange,
                    symboltoken=(
                        symboltoken
                    ),
                    timeframe=(
                        timeframe
                    ),
                    end_time=(
                        end_time
                    ),
                )
            )

        return results

    def fetch_all_with_capture(
        self,
        exchange,
        symboltoken,
        end_time=None,
    ):
        """
        Return existing DataFrames plus the same captured Angel rows.
        """

        dataframes = {}
        rows = {}
        metadata = {}
        diagnostics = {}

        for timeframe in TIMEFRAME_CONFIG:
            capture_key = (
                str(
                    exchange
                ).strip().upper(),
                str(
                    symboltoken
                ).strip(),
                timeframe,
            )

            try:
                response = (
                    self._request_historical(
                        exchange,
                        symboltoken,
                        timeframe,
                        end_time=end_time,
                    )
                )

                raw = response.get(
                    "data",
                    [],
                )

                rows[
                    timeframe
                ] = tuple(
                    tuple(
                        item
                    )
                    for item
                    in raw
                )

                dataframes[
                    timeframe
                ] = (
                    normalize_angel_candles(
                        raw
                    )
                )

                capture_metadata = (
                    self._capture_cache_status.get(
                        capture_key,
                        {
                            "cache_status": (
                                "UNKNOWN"
                            ),
                            "captured": (
                                True
                            ),
                            "provider_source": (
                                "UNKNOWN"
                            ),
                            "cache_write_status": (
                                "UNKNOWN"
                            ),
                        },
                    )
                )

                metadata[
                    timeframe
                ] = {
                    **capture_metadata,
                    "captured": (
                        True
                    ),
                    "requested_until": (
                        end_time.isoformat()
                        if isinstance(
                            end_time,
                            datetime,
                        )
                        else (
                            capture_metadata.get(
                                "requested_until"
                            )
                        )
                    ),
                }

                diagnostics[
                    timeframe
                ] = (
                    self._request_diagnostics.get(
                        capture_key,
                        {},
                    )
                )

            except Exception as exc:
                (
                    provider_throttled,
                    failure_reason,
                ) = (
                    classify_market_data_exception(
                        exc
                    )
                )

                rows[
                    timeframe
                ] = ()

                metadata[
                    timeframe
                ] = {
                    "captured": (
                        False
                    ),
                    "error": (
                        type(
                            exc
                        ).__name__
                    ),
                    "failure_reason": (
                        failure_reason
                    ),
                    "provider_throttled": (
                        provider_throttled
                    ),
                }

                diagnostics[
                    timeframe
                ] = (
                    self._request_diagnostics.get(
                        capture_key,
                        {},
                    )
                )

        return {
            "dataframes": (
                dataframes
            ),
            "rows_by_timeframe": (
                rows
            ),
            "cache_metadata": (
                metadata
            ),
            "request_diagnostics": (
                diagnostics
            ),
        }
