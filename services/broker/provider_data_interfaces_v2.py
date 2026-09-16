"""Provider-neutral read-only data capability protocols.

No provider implementation lives here. These interfaces intentionally
separate instrument resolution, REST history, quote/depth and streaming.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime
from typing import Any, Protocol, runtime_checkable


ProviderInstrument = Mapping[str, Any]
MarketDataRecord = Mapping[str, Any]


@runtime_checkable
class InstrumentResolverV2(Protocol):
    """Resolve a canonical market request to one provider instrument."""

    def resolve(
        self,
        *,
        market_symbol: str,
        instrument_type: str,
        as_of: datetime | None = None,
        expiry: date | None = None,
        strike: float | None = None,
        option_type: str | None = None,
    ) -> ProviderInstrument:
        ...


@runtime_checkable
class HistoricalDataProviderV2(Protocol):
    """Read-only historical candle capability."""

    def get_candles(
        self,
        instrument: ProviderInstrument,
        *,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> Sequence[MarketDataRecord]:
        ...


@runtime_checkable
class QuoteDepthProviderV2(Protocol):
    """Read-only executable quote/depth capability."""

    def get_quote(
        self,
        instrument: ProviderInstrument,
    ) -> MarketDataRecord:
        ...

    def get_depth(
        self,
        instrument: ProviderInstrument,
    ) -> MarketDataRecord:
        ...


@runtime_checkable
class StreamingMarketDataProviderV2(Protocol):
    """Shared streaming subscription capability."""

    def subscribe(
        self,
        instruments: Sequence[ProviderInstrument],
        callback: Callable[
            [MarketDataRecord],
            None,
        ],
    ) -> str:
        ...

    def unsubscribe(
        self,
        subscription_id: str,
    ) -> None:
        ...

    def close(self) -> None:
        ...
