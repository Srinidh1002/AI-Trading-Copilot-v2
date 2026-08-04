"""Pure Angel One spot/candle normalization for the canonical PAPER path.

This module never owns a client and never calls a provider.  Callers pass
captured responses and explicit timestamps, so provider failures cannot become
fresh observations merely by reaching this boundary.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from services.contracts.market_candle_series_v1 import MarketCandleSeriesV1
from services.contracts.market_candle_v1 import MarketCandleV1
from services.contracts.market_data_provenance_v1 import MarketDataProvenanceV1
from services.paper_orchestration.certified_live_provider_readers import CertifiedIndexMarketSpecV1


IST = ZoneInfo("Asia/Kolkata")
_INTERVALS = {"5m": 5, "15m": 15, "1h": 60, "1d": 1440}
_REQUIRED = tuple(_INTERVALS)


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(name)
    return value


def _number(value: object, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(name)
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(name) from exc
    if not math.isfinite(result) or (result <= 0 if positive else result < 0):
        raise ValueError(name)
    return result


def _spec(value: object) -> CertifiedIndexMarketSpecV1:
    if type(value) is not CertifiedIndexMarketSpecV1:
        raise TypeError("market_spec")
    return value


def _timestamp(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        raise ValueError("candle timestamp")
    # Angel historical timestamps are exchange-local when no offset is sent.
    return parsed.replace(tzinfo=IST) if parsed.tzinfo is None else parsed


@dataclass(frozen=True, slots=True)
class AngelLiveSpotObservationV1:
    underlying_symbol: str
    exchange: str
    symboltoken: str
    option_exchange: str
    price: float | None
    provider_timestamp: datetime | None
    evaluated_at: datetime
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    provider_state: str = "OK"
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (self.underlying_symbol, self.exchange, self.symboltoken, self.option_exchange) not in {("NIFTY", "NSE", "99926000", "NFO"), ("SENSEX", "BSE", "99919000", "BFO")}:
            raise ValueError("market identity")
        _aware(self.evaluated_at, "evaluated_at")
        if self.provider_timestamp is not None:
            _aware(self.provider_timestamp, "provider_timestamp")
        if self.price is not None:
            _number(self.price, "price", positive=True)
        if self.price is None and not self.blockers:
            raise ValueError("missing spot requires blocker")
        if self.execution_mode != "PAPER" or self.live_execution_eligible:
            raise ValueError("PAPER-only observation")


@dataclass(frozen=True, slots=True)
class AngelLiveMarketObservationV1:
    spot: AngelLiveSpotObservationV1
    candle_series: tuple[MarketCandleSeriesV1, ...]
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.spot) is not AngelLiveSpotObservationV1 or not isinstance(self.candle_series, tuple):
            raise TypeError("typed observation")
        expected = (self.spot.underlying_symbol, self.spot.exchange)
        names = tuple(item.timeframe for item in self.candle_series)
        if names != tuple(item for item in _REQUIRED if item in names) or len(names) != len(set(names)):
            raise ValueError("timeframe order")
        if any(type(item) is not MarketCandleSeriesV1 or (item.underlying_symbol, item.exchange) != expected for item in self.candle_series):
            raise ValueError("series identity")
        missing = set(_REQUIRED) - set(names)
        if missing and not self.blockers:
            raise ValueError("missing timeframe requires blocker")


def normalize_angel_spot_response(*, response: object, market_spec: CertifiedIndexMarketSpecV1, provider_timestamp: datetime | None, evaluated_at: datetime, provider_state: str = "OK", blockers: tuple[str, ...] = (), warnings: tuple[str, ...] = ()) -> AngelLiveSpotObservationV1:
    spec = _spec(market_spec); _aware(evaluated_at, "evaluated_at")
    if provider_timestamp is not None: _aware(provider_timestamp, "provider_timestamp")
    if not isinstance(response, Mapping):
        return AngelLiveSpotObservationV1(spec.underlying_symbol, spec.exchange, spec.symboltoken, spec.option_exchange, None, provider_timestamp, evaluated_at, blockers=tuple(blockers) or ("SPOT_RESPONSE_UNAVAILABLE",), warnings=tuple(warnings), provider_state=provider_state)
    data = response.get("data")
    if not isinstance(data, Mapping):
        return AngelLiveSpotObservationV1(spec.underlying_symbol, spec.exchange, spec.symboltoken, spec.option_exchange, None, provider_timestamp, evaluated_at, blockers=tuple(blockers) or ("SPOT_RESPONSE_MALFORMED",), warnings=tuple(warnings), provider_state=provider_state)
    for key, expected in (("tradingsymbol", spec.underlying_symbol), ("exchange", spec.exchange), ("symboltoken", spec.symboltoken)):
        actual = data.get(key)
        if actual is not None and str(actual).strip().upper() != expected:
            raise ValueError(f"spot {key} identity mismatch")
    price = data.get("ltp", data.get("last_price", data.get("close")))
    try: price = _number(price, "spot price", positive=True)
    except ValueError: return AngelLiveSpotObservationV1(spec.underlying_symbol, spec.exchange, spec.symboltoken, spec.option_exchange, None, provider_timestamp, evaluated_at, blockers=tuple(blockers) or ("SPOT_PRICE_INVALID",), warnings=tuple(warnings), provider_state=provider_state)
    if provider_timestamp is None:
        return AngelLiveSpotObservationV1(spec.underlying_symbol, spec.exchange, spec.symboltoken, spec.option_exchange, None, None, evaluated_at, blockers=tuple(blockers) or ("SPOT_PROVIDER_TIMESTAMP_MISSING",), warnings=tuple(warnings), provider_state=provider_state)
    return AngelLiveSpotObservationV1(spec.underlying_symbol, spec.exchange, spec.symboltoken, spec.option_exchange, price, provider_timestamp, evaluated_at, blockers=tuple(blockers), warnings=tuple(warnings), provider_state=provider_state)


def normalize_angel_candle_series(*, rows: object, market_spec: CertifiedIndexMarketSpecV1, timeframe: str, provider_timestamp: datetime, evaluated_at: datetime, provider: str = "ANGEL_ONE", is_cached: bool = False, cache_age_seconds: float | None = None) -> MarketCandleSeriesV1:
    spec = _spec(market_spec); _aware(provider_timestamp, "provider_timestamp"); _aware(evaluated_at, "evaluated_at")
    if timeframe not in _INTERVALS: raise ValueError("unsupported timeframe")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise TypeError("candle rows")
    provenance = MarketDataProvenanceV1(
        provider=provider,
        provider_symbol=spec.underlying_symbol,
        provider_exchange=spec.exchange,
        source_type="CACHE" if is_cached else "LIVE",
        fetched_at=provider_timestamp,
        received_at=evaluated_at,
        is_cached=is_cached,
        cache_age_seconds=cache_age_seconds,
        provider_request_id=None,
        warnings=(),
    )
    candles: list[MarketCandleV1] = []
    seen: set[datetime] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, (list, tuple)) or len(row) < 6: raise ValueError("malformed Angel candle row")
        start = _timestamp(row[0])
        if start in seen: raise ValueError("duplicate candle timestamp")
        seen.add(start)
        if start > evaluated_at: raise ValueError("future candle")
        o, h, l, c, v = (_number(row[n], "candle value", positive=n < 4) for n in range(1, 6))
        end = start + timedelta(minutes=_INTERVALS[timeframe])
        if end > evaluated_at: continue
        candles.append(MarketCandleV1(f"angel:{spec.symboltoken}:{timeframe}:{start.isoformat()}", spec.underlying_symbol, spec.exchange, timeframe, start, end, o, h, l, c, v, True, provenance))
    candles.sort(key=lambda item: item.start_at)
    blockers = ("EMPTY_OR_FORMING_CANDLE_SERIES",) if not candles else ()
    return MarketCandleSeriesV1(f"angel:{spec.symboltoken}:{timeframe}:{provider_timestamp.isoformat()}", spec.underlying_symbol, spec.exchange, timeframe, tuple(candles), None, None, evaluated_at, blockers=blockers)


def normalize_angel_live_observation(*, spot_response: object, candle_rows_by_timeframe: Mapping[str, object], market_spec: CertifiedIndexMarketSpecV1, provider_timestamp: datetime | None, evaluated_at: datetime, provider_state: str = "OK", blockers: tuple[str, ...] = (), warnings: tuple[str, ...] = ()) -> AngelLiveMarketObservationV1:
    spot = normalize_angel_spot_response(response=spot_response, market_spec=market_spec, provider_timestamp=provider_timestamp, evaluated_at=evaluated_at, provider_state=provider_state, blockers=blockers, warnings=warnings)
    if provider_timestamp is None:
        return AngelLiveMarketObservationV1(spot, (), blockers=tuple(spot.blockers) + ("CANDLE_PROVIDER_TIMESTAMP_MISSING",))
    series = tuple(normalize_angel_candle_series(rows=candle_rows_by_timeframe[name], market_spec=market_spec, timeframe=name, provider_timestamp=provider_timestamp, evaluated_at=evaluated_at) for name in _REQUIRED if name in candle_rows_by_timeframe)
    missing = tuple(f"TIMEFRAME_UNAVAILABLE_{name}" for name in _REQUIRED if name not in candle_rows_by_timeframe)
    return AngelLiveMarketObservationV1(spot, series, blockers=tuple(dict.fromkeys((*spot.blockers, *missing))), warnings=tuple(warnings))
