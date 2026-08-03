"""Immutable shared NIFTY/SENSEX context for one certified PAPER cycle."""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from services.contracts.broader_market_intelligence_result_v1 import BroaderMarketIntelligenceResultV1
from services.contracts.market_candle_series_v1 import MarketCandleSeriesV1
from services.contracts.india_vix_capture_result_v1 import IndiaVixCaptureResultV1


_MARKETS = (("NIFTY", "NSE"), ("SENSEX", "BSE"))
_TIMEFRAMES = ("5m", "15m", "1h", "1d")
_SECRET_WORDS = ("secret", "password", "pin", "jwt", "totp", "authorization")


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(name)
    return value


def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    result = tuple(" ".join(item.split()) for item in value if isinstance(item, str) and item.strip())
    if len(result) != len(value) or len(result) != len(set(result)):
        raise ValueError(name)
    return result


def _safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(any(word in str(key).lower() for word in _SECRET_WORDS) for key in value):
            raise ValueError("unsafe metadata")
        return MappingProxyType({str(key): _safe(item) for key, item in sorted(value.items())})
    if isinstance(value, (tuple, list)):
        return tuple(_safe(item) for item in value)
    if value is None or isinstance(value, (str, bool, int, float, datetime)):
        return value
    raise TypeError("unsafe metadata")


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _series(value: object, identity: tuple[str, str], name: str) -> Mapping[str, MarketCandleSeriesV1]:
    if not isinstance(value, Mapping):
        raise TypeError(name)
    items = tuple(value.items())
    keys = tuple(key for key, _ in items)
    if keys != tuple(item for item in _TIMEFRAMES if item in keys):
        raise ValueError(name)
    result: dict[str, MarketCandleSeriesV1] = {}
    for timeframe, series in items:
        if timeframe not in _TIMEFRAMES or type(series) is not MarketCandleSeriesV1:
            raise TypeError(name)
        if (series.underlying_symbol, series.exchange, series.timeframe) != (*identity, timeframe):
            raise ValueError(name)
        result[timeframe] = series
    return MappingProxyType(result)


@dataclass(frozen=True, slots=True)
class CertifiedSharedMarketContextV1:
    cycle_id: str
    evaluated_at: datetime
    nifty_candle_series: Mapping[str, MarketCandleSeriesV1]
    sensex_candle_series: Mapping[str, MarketCandleSeriesV1]
    nifty_broader_market: BroaderMarketIntelligenceResultV1 | None
    sensex_broader_market: BroaderMarketIntelligenceResultV1 | None
    source_timestamps: Mapping[str, datetime]
    india_vix_capture: IndiaVixCaptureResultV1 | None = None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    cache_metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = "certified_shared_market_context.v1"

    def __post_init__(self) -> None:
        if not isinstance(self.cycle_id, str) or not self.cycle_id.strip():
            raise ValueError("cycle_id")
        _aware(self.evaluated_at, "evaluated_at")
        object.__setattr__(self, "nifty_candle_series", _series(self.nifty_candle_series, _MARKETS[0], "nifty_candle_series"))
        object.__setattr__(self, "sensex_candle_series", _series(self.sensex_candle_series, _MARKETS[1], "sensex_candle_series"))
        for name, identity in (("nifty_broader_market", _MARKETS[0]), ("sensex_broader_market", _MARKETS[1])):
            value = getattr(self, name)
            if value is not None and (type(value) is not BroaderMarketIntelligenceResultV1 or (value.underlying_symbol, value.exchange) != identity):
                raise ValueError(name)
        timestamps = {str(key): _aware(value, "source_timestamps") for key, value in self.source_timestamps.items()}
        if self.india_vix_capture is not None and type(self.india_vix_capture) is not IndiaVixCaptureResultV1:
            raise ValueError("india_vix_capture")
        if tuple(timestamps) != tuple(sorted(timestamps)):
            raise ValueError("source_timestamps")
        object.__setattr__(self, "source_timestamps", MappingProxyType(timestamps))
        object.__setattr__(self, "blockers", _messages(self.blockers, "blockers"))
        object.__setattr__(self, "warnings", _messages(self.warnings, "warnings"))
        object.__setattr__(self, "cache_metadata", _safe(self.cache_metadata))
        if self.schema_version != "certified_shared_market_context.v1":
            raise ValueError("schema_version")

    def for_market(self, underlying_symbol: str, exchange: str) -> BroaderMarketIntelligenceResultV1 | None:
        if (underlying_symbol, exchange) == _MARKETS[0]:
            return self.nifty_broader_market
        if (underlying_symbol, exchange) == _MARKETS[1]:
            return self.sensex_broader_market
        raise ValueError("market identity")

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "evaluated_at": self.evaluated_at.isoformat(),
            "markets": [
                {"underlying_symbol": symbol, "exchange": exchange, "timeframes": list(series)}
                for (symbol, exchange), series in (( _MARKETS[0], self.nifty_candle_series), (_MARKETS[1], self.sensex_candle_series))
            ],
            "nifty_broader_market": self.nifty_broader_market.to_dict() if self.nifty_broader_market else None,
            "sensex_broader_market": self.sensex_broader_market.to_dict() if self.sensex_broader_market else None,
            "source_timestamps": {key: value.isoformat() for key, value in self.source_timestamps.items()},
            "india_vix_capture": self.india_vix_capture.to_dict() if self.india_vix_capture else None,
            "blockers": list(self.blockers), "warnings": list(self.warnings),
            "cache_metadata": _plain(self.cache_metadata), "schema_version": self.schema_version,
        }
