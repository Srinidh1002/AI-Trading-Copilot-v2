"""Provider-neutral in-process cache for normalized five-market data.

The hub performs no authentication, network I/O, provider selection or
silent fallback. Callers must explicitly name the provider they want.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
from threading import RLock

from services.contracts.market_data_v2 import (
    MarketCandleV2,
    MarketDataProvenanceV2,
    MarketDepthV2,
    MarketQuoteV2,
    ProviderHealthV2,
)


class MarketDataUnavailableError(
    RuntimeError
):
    pass


class StaleMarketDataError(
    MarketDataUnavailableError
):
    pass


class IncompleteMarketDataError(
    MarketDataUnavailableError
):
    pass


def _provider_name(
    value: object,
) -> str:
    if not isinstance(value, str):
        raise ValueError(
            "Provider is required."
        )

    value = " ".join(
        value.upper().split()
    )

    if not value:
        raise ValueError(
            "Provider is required."
        )

    return value


def _instrument_key(
    *,
    provider: str,
    market_symbol: str,
    exchange: str,
    instrument_type: str,
    canonical_instrument_id: str,
) -> tuple[
    str,
    str,
    str,
    str,
    str,
]:
    return (
        _provider_name(provider),
        market_symbol,
        exchange,
        instrument_type,
        canonical_instrument_id,
    )


def _record_key(
    record: (
        MarketQuoteV2
        | MarketDepthV2
        | MarketCandleV2
    ),
) -> tuple[
    str,
    str,
    str,
    str,
    str,
]:
    return _instrument_key(
        provider=record.provenance.provider,
        market_symbol=record.market_symbol,
        exchange=record.exchange,
        instrument_type=record.instrument_type,
        canonical_instrument_id=(
            record.canonical_instrument_id
        ),
    )


def _validate_freshness(
    provenance: MarketDataProvenanceV2,
    *,
    max_age_seconds: float,
    now: datetime | None,
) -> None:
    if (
        not isinstance(
            max_age_seconds,
            (int, float),
        )
        or isinstance(
            max_age_seconds,
            bool,
        )
        or not math.isfinite(
            max_age_seconds
        )
        or max_age_seconds < 0
    ):
        raise ValueError(
            "Invalid freshness limit."
        )

    if now is None:
        now = datetime.now(
            timezone.utc
        )

    if (
        not isinstance(
            now,
            datetime,
        )
        or now.tzinfo is None
        or now.utcoffset() is None
    ):
        raise ValueError(
            "Freshness reference must be timezone-aware."
        )

    age = (
        now
        - provenance.observed_at
    ).total_seconds()

    if age < 0:
        raise MarketDataUnavailableError(
            "MARKET_DATA_TIMESTAMP_IN_FUTURE"
        )

    if age > max_age_seconds:
        raise StaleMarketDataError(
            "STALE_MARKET_DATA"
        )


class SharedMarketDataHubV2:
    """Thread-safe normalized cache with explicit provider isolation."""

    def __init__(
        self,
        *,
        max_candles_per_series: int = 500,
    ) -> None:
        if (
            not isinstance(
                max_candles_per_series,
                int,
            )
            or isinstance(
                max_candles_per_series,
                bool,
            )
            or max_candles_per_series < 1
        ):
            raise ValueError(
                "Invalid candle cache size."
            )

        self._lock = RLock()

        self._max_candles = (
            max_candles_per_series
        )

        self._quotes: dict[
            tuple[str, str, str, str, str],
            MarketQuoteV2,
        ] = {}

        self._depth: dict[
            tuple[str, str, str, str, str],
            MarketDepthV2,
        ] = {}

        self._candles: dict[
            tuple[
                str,
                str,
                str,
                str,
                str,
                str,
            ],
            list[MarketCandleV2],
        ] = {}

        self._health: dict[
            str,
            ProviderHealthV2,
        ] = {}

    def publish_quote(
        self,
        quote: MarketQuoteV2,
    ) -> None:
        if not isinstance(
            quote,
            MarketQuoteV2,
        ):
            raise TypeError(
                "Expected MarketQuoteV2."
            )

        with self._lock:
            self._quotes[
                _record_key(quote)
            ] = quote

    def publish_depth(
        self,
        depth: MarketDepthV2,
    ) -> None:
        if not isinstance(
            depth,
            MarketDepthV2,
        ):
            raise TypeError(
                "Expected MarketDepthV2."
            )

        with self._lock:
            self._depth[
                _record_key(depth)
            ] = depth

    def publish_candle(
        self,
        candle: MarketCandleV2,
    ) -> None:
        if not isinstance(
            candle,
            MarketCandleV2,
        ):
            raise TypeError(
                "Expected MarketCandleV2."
            )

        base_key = _record_key(
            candle
        )

        key = (
            *base_key,
            candle.timeframe,
        )

        with self._lock:
            series = list(
                self._candles.get(
                    key,
                    [],
                )
            )

            by_start = {
                item.start_at: item
                for item in series
            }

            by_start[
                candle.start_at
            ] = candle

            series = sorted(
                by_start.values(),
                key=lambda item: (
                    item.start_at
                ),
            )

            self._candles[key] = (
                series[
                    -self._max_candles:
                ]
            )

    def set_provider_health(
        self,
        health: ProviderHealthV2,
    ) -> None:
        if not isinstance(
            health,
            ProviderHealthV2,
        ):
            raise TypeError(
                "Expected ProviderHealthV2."
            )

        with self._lock:
            self._health[
                health.provider
            ] = health

    def get_quote(
        self,
        *,
        provider: str,
        market_symbol: str,
        exchange: str,
        instrument_type: str,
        canonical_instrument_id: str,
        max_age_seconds: float,
        now: datetime | None = None,
    ) -> MarketQuoteV2:
        key = _instrument_key(
            provider=provider,
            market_symbol=market_symbol,
            exchange=exchange,
            instrument_type=instrument_type,
            canonical_instrument_id=(
                canonical_instrument_id
            ),
        )

        with self._lock:
            quote = self._quotes.get(
                key
            )

        if quote is None:
            raise MarketDataUnavailableError(
                "QUOTE_UNAVAILABLE"
            )

        _validate_freshness(
            quote.provenance,
            max_age_seconds=max_age_seconds,
            now=now,
        )

        return quote

    def get_depth(
        self,
        *,
        provider: str,
        market_symbol: str,
        exchange: str,
        instrument_type: str,
        canonical_instrument_id: str,
        max_age_seconds: float,
        now: datetime | None = None,
    ) -> MarketDepthV2:
        key = _instrument_key(
            provider=provider,
            market_symbol=market_symbol,
            exchange=exchange,
            instrument_type=instrument_type,
            canonical_instrument_id=(
                canonical_instrument_id
            ),
        )

        with self._lock:
            depth = self._depth.get(
                key
            )

        if depth is None:
            raise MarketDataUnavailableError(
                "DEPTH_UNAVAILABLE"
            )

        _validate_freshness(
            depth.provenance,
            max_age_seconds=max_age_seconds,
            now=now,
        )

        return depth

    def get_candles(
        self,
        *,
        provider: str,
        market_symbol: str,
        exchange: str,
        instrument_type: str,
        canonical_instrument_id: str,
        timeframe: str,
        count: int,
        require_complete: bool = True,
        max_age_seconds: float | None = None,
        now: datetime | None = None,
    ) -> tuple[
        MarketCandleV2,
        ...,
    ]:
        if (
            not isinstance(
                count,
                int,
            )
            or isinstance(
                count,
                bool,
            )
            or count < 1
        ):
            raise ValueError(
                "Invalid candle count."
            )

        key = (
            *_instrument_key(
                provider=provider,
                market_symbol=market_symbol,
                exchange=exchange,
                instrument_type=instrument_type,
                canonical_instrument_id=(
                    canonical_instrument_id
                ),
            ),
            timeframe.lower(),
        )

        with self._lock:
            series = tuple(
                self._candles.get(
                    key,
                    (),
                )
            )

        if require_complete:
            series = tuple(
                candle
                for candle in series
                if candle.is_complete
            )

        if len(series) < count:
            raise IncompleteMarketDataError(
                "INSUFFICIENT_CANDLE_HISTORY"
            )

        selected = series[
            -count:
        ]

        if max_age_seconds is not None:
            _validate_freshness(
                selected[-1].provenance,
                max_age_seconds=(
                    max_age_seconds
                ),
                now=now,
            )

        return selected

    def get_provider_health(
        self,
        provider: str,
    ) -> ProviderHealthV2:
        provider_name = _provider_name(
            provider
        )

        with self._lock:
            health = self._health.get(
                provider_name
            )

        if health is None:
            raise MarketDataUnavailableError(
                "PROVIDER_HEALTH_UNAVAILABLE"
            )

        return health

    def snapshot_counts(
        self,
    ) -> dict[str, int]:
        with self._lock:
            return {
                "quotes": len(
                    self._quotes
                ),
                "depth": len(
                    self._depth
                ),
                "candle_series": len(
                    self._candles
                ),
                "provider_health": len(
                    self._health
                ),
            }
