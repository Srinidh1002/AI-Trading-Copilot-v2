"""Canonical provider-neutral market-data contracts for the five-market universe."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import math
import re

from services.core.five_market_universe_v2 import (
    get_target_market,
)


_SOURCE_TYPES = {
    "LIVE",
    "CACHE",
    "REPLAY",
    "TEST",
}

_INSTRUMENT_TYPES = {
    "UNDERLYING",
    "FUTURE",
    "OPTION",
}

_TIMEFRAMES = {
    "1m",
    "3m",
    "5m",
    "15m",
    "30m",
    "1h",
    "1d",
}

_PROVIDER_HEALTH = {
    "HEALTHY",
    "DEGRADED",
    "UNAVAILABLE",
}

_REASON_CODE = re.compile(
    r"^[A-Z0-9_-]+$"
)


def _normalise(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    value = " ".join(
        value.upper().split()
    )

    return value or None


def _nonempty(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    value = value.strip()

    return value or None


def _aware(value: object) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def _finite(
    value: object,
) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _positive(
    value: object,
) -> bool:
    return (
        _finite(value)
        and value > 0
    )


def _nonnegative(
    value: object,
) -> bool:
    return (
        _finite(value)
        and value >= 0
    )


def _validate_market_exchange(
    market_symbol: object,
    exchange: object,
    instrument_type: object,
) -> tuple[str, str, str]:
    symbol = _normalise(
        market_symbol
    )
    exchange_name = _normalise(
        exchange
    )
    instrument = _normalise(
        instrument_type
    )

    if symbol is None:
        raise ValueError(
            "Invalid market symbol."
        )

    if exchange_name is None:
        raise ValueError(
            "Invalid exchange."
        )

    if instrument not in _INSTRUMENT_TYPES:
        raise ValueError(
            "Unsupported instrument type."
        )

    market = get_target_market(
        symbol
    )

    if instrument == "UNDERLYING":
        expected_exchange = (
            market.underlying_exchange
        )
    else:
        expected_exchange = (
            market.derivative_exchange
        )

    if exchange_name != expected_exchange:
        raise ValueError(
            "Market-data exchange mismatch."
        )

    return (
        market.symbol,
        exchange_name,
        instrument,
    )


@dataclass(frozen=True, slots=True)
class MarketDataProvenanceV2:
    provider: str
    provider_symbol: str | None
    provider_exchange: str | None
    source_type: str
    observed_at: datetime
    received_at: datetime
    is_cached: bool = False
    cache_age_seconds: float | None = None
    provider_request_id: str | None = None
    warnings: tuple[str, ...] = ()
    schema_version: str = (
        "market_data_provenance.v2"
    )

    def __post_init__(self) -> None:
        provider = _normalise(
            self.provider
        )
        source_type = _normalise(
            self.source_type
        )

        if provider is None:
            raise ValueError(
                "Provider is required."
            )

        if source_type not in _SOURCE_TYPES:
            raise ValueError(
                "Invalid source type."
            )

        if not _aware(self.observed_at):
            raise ValueError(
                "Observed timestamp must be timezone-aware."
            )

        if not _aware(self.received_at):
            raise ValueError(
                "Received timestamp must be timezone-aware."
            )

        if self.received_at < self.observed_at:
            raise ValueError(
                "Received timestamp precedes observed timestamp."
            )

        if not isinstance(
            self.is_cached,
            bool,
        ):
            raise ValueError(
                "Invalid cache flag."
            )

        if source_type == "CACHE" and not self.is_cached:
            raise ValueError(
                "CACHE source must be marked cached."
            )

        if self.is_cached:
            if not _nonnegative(
                self.cache_age_seconds
            ):
                raise ValueError(
                    "Cached data requires non-negative cache age."
                )
        elif self.cache_age_seconds is not None:
            raise ValueError(
                "Non-cached data cannot carry cache age."
            )

        if (
            self.provider_request_id is not None
            and _nonempty(
                self.provider_request_id
            )
            is None
        ):
            raise ValueError(
                "Invalid provider request id."
            )

        if (
            self.schema_version
            != "market_data_provenance.v2"
        ):
            raise ValueError(
                "Invalid provenance schema."
            )

        if not isinstance(
            self.warnings,
            tuple,
        ):
            raise ValueError(
                "Warnings must be a tuple."
            )

        object.__setattr__(
            self,
            "provider",
            provider,
        )
        object.__setattr__(
            self,
            "source_type",
            source_type,
        )
        object.__setattr__(
            self,
            "provider_symbol",
            (
                _nonempty(
                    self.provider_symbol
                )
                if self.provider_symbol
                is not None
                else None
            ),
        )
        object.__setattr__(
            self,
            "provider_exchange",
            (
                _nonempty(
                    self.provider_exchange
                )
                if self.provider_exchange
                is not None
                else None
            ),
        )
        object.__setattr__(
            self,
            "provider_request_id",
            (
                _nonempty(
                    self.provider_request_id
                )
                if self.provider_request_id
                is not None
                else None
            ),
        )
        object.__setattr__(
            self,
            "warnings",
            tuple(self.warnings),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "provider_symbol": (
                self.provider_symbol
            ),
            "provider_exchange": (
                self.provider_exchange
            ),
            "source_type": self.source_type,
            "observed_at": (
                self.observed_at.isoformat()
            ),
            "received_at": (
                self.received_at.isoformat()
            ),
            "is_cached": self.is_cached,
            "cache_age_seconds": (
                self.cache_age_seconds
            ),
            "provider_request_id": (
                self.provider_request_id
            ),
            "warnings": list(
                self.warnings
            ),
            "schema_version": (
                self.schema_version
            ),
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
        )


@dataclass(frozen=True, slots=True)
class MarketQuoteV2:
    quote_id: str
    market_symbol: str
    exchange: str
    instrument_type: str
    canonical_instrument_id: str
    last_price: float
    bid_price: float | None
    ask_price: float | None
    volume: float | None
    open_interest: float | None
    provenance: MarketDataProvenanceV2
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    warnings: tuple[str, ...] = ()
    schema_version: str = "market_quote.v2"

    def __post_init__(self) -> None:
        (
            symbol,
            exchange,
            instrument,
        ) = _validate_market_exchange(
            self.market_symbol,
            self.exchange,
            self.instrument_type,
        )

        if _nonempty(self.quote_id) is None:
            raise ValueError(
                "Quote id is required."
            )

        canonical_id = _nonempty(
            self.canonical_instrument_id
        )

        if canonical_id is None:
            raise ValueError(
                "Canonical instrument id is required."
            )

        if not _positive(
            self.last_price
        ):
            raise ValueError(
                "Invalid last price."
            )

        for value in (
            self.bid_price,
            self.ask_price,
        ):
            if (
                value is not None
                and not _positive(value)
            ):
                raise ValueError(
                    "Invalid bid/ask price."
                )

        if (
            self.bid_price is not None
            and self.ask_price is not None
            and self.bid_price
            > self.ask_price
        ):
            raise ValueError(
                "Crossed quote."
            )

        for value in (
            self.volume,
            self.open_interest,
        ):
            if (
                value is not None
                and not _nonnegative(value)
            ):
                raise ValueError(
                    "Invalid quote quantity field."
                )

        if not isinstance(
            self.provenance,
            MarketDataProvenanceV2,
        ):
            raise ValueError(
                "Invalid quote provenance."
            )

        if self.execution_mode != "PAPER":
            raise ValueError(
                "Market quote is PAPER only."
            )

        if self.live_execution_eligible is not False:
            raise ValueError(
                "Live execution is not eligible."
            )

        if self.schema_version != "market_quote.v2":
            raise ValueError(
                "Invalid quote schema."
            )

        object.__setattr__(
            self,
            "market_symbol",
            symbol,
        )
        object.__setattr__(
            self,
            "exchange",
            exchange,
        )
        object.__setattr__(
            self,
            "instrument_type",
            instrument,
        )
        object.__setattr__(
            self,
            "canonical_instrument_id",
            canonical_id,
        )
        object.__setattr__(
            self,
            "warnings",
            tuple(self.warnings),
        )


@dataclass(frozen=True, slots=True)
class MarketDepthLevelV2:
    price: float
    quantity: float
    orders: int | None = None

    def __post_init__(self) -> None:
        if not _positive(
            self.price
        ):
            raise ValueError(
                "Invalid depth price."
            )

        if not _nonnegative(
            self.quantity
        ):
            raise ValueError(
                "Invalid depth quantity."
            )

        if (
            self.orders is not None
            and (
                not isinstance(
                    self.orders,
                    int,
                )
                or isinstance(
                    self.orders,
                    bool,
                )
                or self.orders < 0
            )
        ):
            raise ValueError(
                "Invalid depth order count."
            )


@dataclass(frozen=True, slots=True)
class MarketDepthV2:
    depth_id: str
    market_symbol: str
    exchange: str
    instrument_type: str
    canonical_instrument_id: str
    bids: tuple[
        MarketDepthLevelV2,
        ...,
    ]
    asks: tuple[
        MarketDepthLevelV2,
        ...,
    ]
    tick_size: float | None
    provenance: MarketDataProvenanceV2
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    warnings: tuple[str, ...] = ()
    schema_version: str = "market_depth.v2"

    def __post_init__(self) -> None:
        (
            symbol,
            exchange,
            instrument,
        ) = _validate_market_exchange(
            self.market_symbol,
            self.exchange,
            self.instrument_type,
        )

        if _nonempty(self.depth_id) is None:
            raise ValueError(
                "Depth id is required."
            )

        canonical_id = _nonempty(
            self.canonical_instrument_id
        )

        if canonical_id is None:
            raise ValueError(
                "Canonical instrument id is required."
            )

        if not isinstance(
            self.bids,
            tuple,
        ) or not isinstance(
            self.asks,
            tuple,
        ):
            raise ValueError(
                "Depth levels must be tuples."
            )

        if not self.bids:
            raise ValueError(
                "Executable depth requires bids."
            )

        if not self.asks:
            raise ValueError(
                "Executable depth requires asks."
            )

        if not all(
            isinstance(
                level,
                MarketDepthLevelV2,
            )
            for level in (
                *self.bids,
                *self.asks,
            )
        ):
            raise ValueError(
                "Invalid depth level."
            )

        bid_prices = [
            level.price
            for level in self.bids
        ]

        ask_prices = [
            level.price
            for level in self.asks
        ]

        if bid_prices != sorted(
            bid_prices,
            reverse=True,
        ):
            raise ValueError(
                "Bids are not descending."
            )

        if ask_prices != sorted(
            ask_prices
        ):
            raise ValueError(
                "Asks are not ascending."
            )

        if (
            bid_prices[0]
            > ask_prices[0]
        ):
            raise ValueError(
                "Crossed depth book."
            )

        if (
            self.tick_size is not None
            and not _positive(
                self.tick_size
            )
        ):
            raise ValueError(
                "Invalid tick size."
            )

        if self.tick_size is not None:
            for price in (
                *bid_prices,
                *ask_prices,
            ):
                ticks = (
                    price
                    / self.tick_size
                )

                if (
                    abs(
                        ticks
                        - round(ticks)
                    )
                    > 1e-6
                ):
                    raise ValueError(
                        "Depth price is not tick aligned."
                    )

        if not isinstance(
            self.provenance,
            MarketDataProvenanceV2,
        ):
            raise ValueError(
                "Invalid depth provenance."
            )

        if self.execution_mode != "PAPER":
            raise ValueError(
                "Market depth is PAPER only."
            )

        if self.live_execution_eligible is not False:
            raise ValueError(
                "Live execution is not eligible."
            )

        if self.schema_version != "market_depth.v2":
            raise ValueError(
                "Invalid depth schema."
            )

        object.__setattr__(
            self,
            "market_symbol",
            symbol,
        )
        object.__setattr__(
            self,
            "exchange",
            exchange,
        )
        object.__setattr__(
            self,
            "instrument_type",
            instrument,
        )
        object.__setattr__(
            self,
            "canonical_instrument_id",
            canonical_id,
        )
        object.__setattr__(
            self,
            "warnings",
            tuple(self.warnings),
        )

    @property
    def best_bid(self) -> float:
        return self.bids[0].price

    @property
    def best_ask(self) -> float:
        return self.asks[0].price


@dataclass(frozen=True, slots=True)
class MarketCandleV2:
    candle_id: str
    market_symbol: str
    exchange: str
    instrument_type: str
    canonical_instrument_id: str
    timeframe: str
    start_at: datetime
    end_at: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    is_complete: bool
    provenance: MarketDataProvenanceV2
    warnings: tuple[str, ...] = ()
    schema_version: str = "market_candle.v2"

    def __post_init__(self) -> None:
        (
            symbol,
            exchange,
            instrument,
        ) = _validate_market_exchange(
            self.market_symbol,
            self.exchange,
            self.instrument_type,
        )

        if _nonempty(self.candle_id) is None:
            raise ValueError(
                "Candle id is required."
            )

        canonical_id = _nonempty(
            self.canonical_instrument_id
        )

        if canonical_id is None:
            raise ValueError(
                "Canonical instrument id is required."
            )

        timeframe = _normalise(
            self.timeframe
        )

        if timeframe is None:
            raise ValueError(
                "Invalid candle timeframe."
            )

        timeframe = timeframe.lower()

        if timeframe not in _TIMEFRAMES:
            raise ValueError(
                "Unsupported candle timeframe."
            )

        if not _aware(
            self.start_at
        ) or not _aware(
            self.end_at
        ):
            raise ValueError(
                "Candle timestamps must be timezone-aware."
            )

        if self.end_at <= self.start_at:
            raise ValueError(
                "Invalid candle interval."
            )

        prices = (
            self.open_price,
            self.high_price,
            self.low_price,
            self.close_price,
        )

        if not all(
            _positive(value)
            for value in prices
        ):
            raise ValueError(
                "Invalid OHLC price."
            )

        if (
            self.high_price
            < max(
                self.open_price,
                self.close_price,
                self.low_price,
            )
        ):
            raise ValueError(
                "Invalid candle high."
            )

        if (
            self.low_price
            > min(
                self.open_price,
                self.close_price,
                self.high_price,
            )
        ):
            raise ValueError(
                "Invalid candle low."
            )

        if not _nonnegative(
            self.volume
        ):
            raise ValueError(
                "Invalid candle volume."
            )

        if not isinstance(
            self.is_complete,
            bool,
        ):
            raise ValueError(
                "Invalid candle completeness."
            )

        if not isinstance(
            self.provenance,
            MarketDataProvenanceV2,
        ):
            raise ValueError(
                "Invalid candle provenance."
            )

        if self.schema_version != "market_candle.v2":
            raise ValueError(
                "Invalid candle schema."
            )

        object.__setattr__(
            self,
            "market_symbol",
            symbol,
        )
        object.__setattr__(
            self,
            "exchange",
            exchange,
        )
        object.__setattr__(
            self,
            "instrument_type",
            instrument,
        )
        object.__setattr__(
            self,
            "canonical_instrument_id",
            canonical_id,
        )
        object.__setattr__(
            self,
            "timeframe",
            timeframe,
        )
        object.__setattr__(
            self,
            "warnings",
            tuple(self.warnings),
        )


@dataclass(frozen=True, slots=True)
class ProviderHealthV2:
    provider: str
    status: str
    checked_at: datetime
    last_success_at: datetime | None
    consecutive_failures: int
    reason_code: str | None = None
    warnings: tuple[str, ...] = ()
    schema_version: str = "provider_health.v2"

    def __post_init__(self) -> None:
        provider = _normalise(
            self.provider
        )
        status = _normalise(
            self.status
        )

        if provider is None:
            raise ValueError(
                "Provider is required."
            )

        if status not in _PROVIDER_HEALTH:
            raise ValueError(
                "Invalid provider health status."
            )

        if not _aware(
            self.checked_at
        ):
            raise ValueError(
                "Health timestamp must be timezone-aware."
            )

        if self.last_success_at is not None:
            if not _aware(
                self.last_success_at
            ):
                raise ValueError(
                    "Last success timestamp must be timezone-aware."
                )

            if (
                self.last_success_at
                > self.checked_at
            ):
                raise ValueError(
                    "Last success cannot be in the future."
                )

        if (
            not isinstance(
                self.consecutive_failures,
                int,
            )
            or isinstance(
                self.consecutive_failures,
                bool,
            )
            or self.consecutive_failures < 0
        ):
            raise ValueError(
                "Invalid consecutive failure count."
            )

        reason = (
            _normalise(
                self.reason_code
            )
            if self.reason_code is not None
            else None
        )

        if (
            reason is not None
            and _REASON_CODE.fullmatch(
                reason
            )
            is None
        ):
            raise ValueError(
                "Invalid provider reason code."
            )

        if status == "HEALTHY":
            if self.consecutive_failures != 0:
                raise ValueError(
                    "Healthy provider cannot have consecutive failures."
                )

            if reason is not None:
                raise ValueError(
                    "Healthy provider cannot have failure reason."
                )

        if (
            status == "UNAVAILABLE"
            and self.consecutive_failures < 1
        ):
            raise ValueError(
                "Unavailable provider requires failure evidence."
            )

        if self.schema_version != "provider_health.v2":
            raise ValueError(
                "Invalid provider health schema."
            )

        object.__setattr__(
            self,
            "provider",
            provider,
        )
        object.__setattr__(
            self,
            "status",
            status,
        )
        object.__setattr__(
            self,
            "reason_code",
            reason,
        )
        object.__setattr__(
            self,
            "warnings",
            tuple(self.warnings),
        )
