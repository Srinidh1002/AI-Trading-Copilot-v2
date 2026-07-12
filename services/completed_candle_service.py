"""
Completed-candle service.

Fetches recent Angel One historical candles and returns
the latest fully completed and integrity-validated candle.

If the initial lookback contains no candle data, the service
progressively searches farther back. This handles weekends,
holidays, and periods outside market hours.

Safety checks:
- Reject malformed broker candle rows
- Validate OHLC relationships
- Reject invalid prices
- Reject negative volume
- Reject invalid timestamps
- Never use a candle that is still forming

Read-only. No orders are placed.
"""

from datetime import (
    datetime,
    timedelta,
)

from services.market_data_validator import (
    MarketDataValidationError,
    validate_candle,
)


INTERVAL_MINUTES = {
    "ONE_MINUTE": 1,
    "THREE_MINUTE": 3,
    "FIVE_MINUTE": 5,
    "TEN_MINUTE": 10,
    "FIFTEEN_MINUTE": 15,
    "THIRTY_MINUTE": 30,
    "ONE_HOUR": 60,
}


class CompletedCandleService:

    def __init__(
        self,
        market_client,
    ):
        self.market_client = market_client

    @staticmethod
    def _parse_timestamp(
        value,
    ):
        """
        Parse common Angel One candle timestamps.
        """

        if isinstance(
            value,
            datetime,
        ):
            return value

        cleaned = str(
            value
        ).strip()

        if not cleaned:
            raise ValueError(
                "Candle timestamp is empty."
            )

        try:
            return datetime.fromisoformat(
                cleaned.replace(
                    "Z",
                    "+00:00",
                )
            )

        except ValueError:
            pass

        formats = (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        )

        for date_format in formats:

            try:
                return datetime.strptime(
                    cleaned,
                    date_format,
                )

            except ValueError:
                continue

        raise ValueError(
            "Unable to parse candle timestamp: "
            f"{value}"
        )

    @staticmethod
    def _normalize_candle(
        row,
    ):
        """
        Convert an Angel One candle row into
        a normalized dictionary.

        Expected row:
        [
            timestamp,
            open,
            high,
            low,
            close,
            volume
        ]
        """

        if (
            not isinstance(
                row,
                (
                    list,
                    tuple,
                ),
            )
            or len(row) < 6
        ):
            raise ValueError(
                "Invalid Angel One candle row."
            )

        return {
            "timestamp": row[0],
            "open": row[1],
            "high": row[2],
            "low": row[3],
            "close": row[4],
            "volume": row[5],
        }

    @staticmethod
    def _validate_and_normalize_candle(
        row,
    ):
        """
        Normalize a raw broker candle and run
        mandatory market-data integrity validation.

        The returned timestamp preserves the broker's
        original representation for compatibility with
        the rest of the application.

        Numeric OHLCV values use the validated,
        normalized values.
        """

        candle = (
            CompletedCandleService
            ._normalize_candle(
                row
            )
        )

        original_timestamp = candle[
            "timestamp"
        ]

        validated = validate_candle(
            candle
        )

        return {
            "timestamp": original_timestamp,
            "open": validated[
                "open"
            ],
            "high": validated[
                "high"
            ],
            "low": validated[
                "low"
            ],
            "close": validated[
                "close"
            ],
            "volume": validated[
                "volume"
            ],
        }

    @staticmethod
    def _align_timezones(
        candle_start,
        current_time,
    ):
        """
        Align timezone-aware and timezone-naive
        datetime values for safe comparison.
        """

        comparison_time = current_time

        if (
            candle_start.tzinfo is not None
            and comparison_time.tzinfo is None
        ):
            comparison_time = (
                comparison_time.replace(
                    tzinfo=candle_start.tzinfo
                )
            )

        elif (
            candle_start.tzinfo is None
            and comparison_time.tzinfo is not None
        ):
            candle_start = (
                candle_start.replace(
                    tzinfo=comparison_time.tzinfo
                )
            )

        return (
            candle_start,
            comparison_time,
        )

    def _fetch_candles(
        self,
        exchange,
        symboltoken,
        interval,
        from_time,
        to_time,
    ):
        """
        Fetch candle rows from Angel One.

        Returns an empty list when the broker
        returns no candle data.
        """

        response = (
            self.market_client
            .get_historical_data(
                exchange=exchange,
                symboltoken=symboltoken,
                interval=interval,
                fromdate=(
                    from_time.strftime(
                        "%Y-%m-%d %H:%M"
                    )
                ),
                todate=(
                    to_time.strftime(
                        "%Y-%m-%d %H:%M"
                    )
                ),
            )
        )

        if not response:
            return []

        rows = response.get(
            "data",
            [],
        )

        if not rows:
            return []

        return rows

    def get_latest_completed_candle(
        self,
        exchange,
        symboltoken,
        interval="FIVE_MINUTE",
        now=None,
        lookback_minutes=60,
    ):
        """
        Return the latest fully completed and
        integrity-validated candle.

        A candle is completed only when:

            candle_start + interval <= current time

        Invalid broker candles are rejected and
        never used for trade confirmation.

        The service first uses the requested lookback.
        If no data exists, it progressively searches
        farther back to handle weekends and holidays.
        """

        interval = str(
            interval
        ).upper()

        if interval not in INTERVAL_MINUTES:
            raise ValueError(
                f"Unsupported interval: {interval}"
            )

        if lookback_minutes <= 0:
            raise ValueError(
                "lookback_minutes must be "
                "greater than zero."
            )

        current_time = (
            now
            if now is not None
            else datetime.now()
        )

        interval_minutes = (
            INTERVAL_MINUTES[
                interval
            ]
        )

        # ---------------------------------
        # PROGRESSIVE SEARCH WINDOWS
        # ---------------------------------

        search_windows = []

        for minutes in (
            lookback_minutes,
            24 * 60,
            3 * 24 * 60,
            7 * 24 * 60,
        ):

            if minutes not in search_windows:
                search_windows.append(
                    minutes
                )

        rows = []

        for search_minutes in search_windows:

            from_time = (
                current_time
                - timedelta(
                    minutes=search_minutes
                )
            )

            rows = self._fetch_candles(
                exchange=exchange,
                symboltoken=symboltoken,
                interval=interval,
                from_time=from_time,
                to_time=current_time,
            )

            if rows:
                break

        if not rows:
            raise RuntimeError(
                "No candle data received "
                "within the fallback lookback window."
            )

        # ---------------------------------
        # VALIDATE AND FILTER COMPLETED
        # CANDLES
        # ---------------------------------

        completed = []

        invalid_candle_count = 0

        for row in rows:

            try:

                candle = (
                    self._validate_and_normalize_candle(
                        row
                    )
                )

                candle_start = (
                    self._parse_timestamp(
                        candle[
                            "timestamp"
                        ]
                    )
                )

                (
                    candle_start,
                    comparison_time,
                ) = self._align_timezones(
                    candle_start=candle_start,
                    current_time=current_time,
                )

            except (
                TypeError,
                ValueError,
                MarketDataValidationError,
            ):

                invalid_candle_count += 1

                continue

            candle_end = (
                candle_start
                + timedelta(
                    minutes=interval_minutes
                )
            )

            if (
                candle_end
                <= comparison_time
            ):

                candle[
                    "_parsed_timestamp"
                ] = candle_start

                completed.append(
                    candle
                )

        # ---------------------------------
        # FAIL CLOSED
        # ---------------------------------

        if not completed:

            if (
                invalid_candle_count
                > 0
            ):
                raise MarketDataValidationError(
                    "No valid completed candle is "
                    "available because received market "
                    "data failed integrity validation."
                )

            raise RuntimeError(
                "No completed candle available "
                "within the fallback lookback window."
            )

        # ---------------------------------
        # SELECT LATEST VALID COMPLETED
        # CANDLE
        # ---------------------------------

        completed.sort(
            key=lambda candle: (
                candle[
                    "_parsed_timestamp"
                ]
            )
        )

        latest = dict(
            completed[-1]
        )

        latest.pop(
            "_parsed_timestamp",
            None,
        )

        return latest