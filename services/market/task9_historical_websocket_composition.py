"""Read-only Task9 historical-cache plus closed-WebSocket evidence seam."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from services.market.task9_live_tick_stream import (
    IST, Task9LiveCandleAggregator, Task9LiveTickJournal,
)
from services.market.live_multi_timeframe_data import required_closed_candle_at


REQUIRED_TIMEFRAMES = ("5m", "15m", "1h", "1d")


@dataclass(frozen=True, slots=True)
class Task9ComposedTimeframeEvidenceV1:
    market: str
    timeframe: str
    required_bar_count: int
    available_bar_count: int
    source_composition: tuple[str, ...]
    earliest_required_timestamp: str | None
    latest_closed_timestamp: str | None
    missing_interval_identities: tuple[str, ...]
    ready: bool
    failure_reason: str | None
    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self):
        if self.market not in {"NIFTY", "SENSEX"} or self.timeframe not in REQUIRED_TIMEFRAMES:
            raise ValueError("Task9 composition identity")
        if self.required_bar_count != 1 or self.available_bar_count < 0:
            raise ValueError("Task9 production bar requirement")
        if self.execution_mode != "PAPER" or self.broker_order_submission is not False or self.live_execution_eligible is not False:
            raise ValueError("Task9 composition must remain PAPER-only")


def _timestamp(row):
    value = row[0] if isinstance(row, (tuple, list)) else row.get("timestamp")
    return datetime.fromisoformat(value) if isinstance(value, str) else value


def _effective_required_candle_at(*, timeframe: str, required_closed_at: datetime) -> datetime:
    """Map shared historical identities to Task9's session-anchored evidence."""
    # The shared historical helper expresses an hourly candle by the preceding
    # clock-aligned start (09:00, 10:00, ...). Task9's cache and WebSocket
    # evidence use the actual regular-session interval starts (09:15, 10:15,
    # ...), so only hourly evidence has this fixed, same-session offset.
    return required_closed_at + timedelta(minutes=15) if timeframe == "1h" else required_closed_at


class Task9HistoricalWebsocketComposition:
    """Composes caller-supplied cache rows with journal rows; no I/O except reads."""
    def __init__(self, *, live_stream_root):
        self.aggregator = Task9LiveCandleAggregator(Task9LiveTickJournal(live_stream_root))

    def compose(self, *, market, trading_date, timeframe, as_of, historical_rows=()):
        if timeframe not in REQUIRED_TIMEFRAMES or market not in {"NIFTY", "SENSEX"}:
            raise ValueError("Task9 composition identity")
        as_of = as_of.astimezone(IST)
        exchange = "NSE" if market == "NIFTY" else "BSE"
        required_closed_at = required_closed_candle_at(
            timeframe,
            as_of,
            exchange=exchange,
        )
        effective_required_at = _effective_required_candle_at(
            timeframe=timeframe,
            required_closed_at=required_closed_at,
        )
        historical = []
        for row in historical_rows:
            try:
                stamp = _timestamp(row).astimezone(IST)
            except (AttributeError, TypeError, ValueError):
                continue
            historical.append((stamp, row))
        websocket = () if timeframe == "1d" else self.aggregator.candles(market=market, trading_date=trading_date, timeframe=timeframe, as_of=as_of)
        certified_websocket_starts = (
            frozenset(self.aggregator.coverage(
                market=market, trading_date=trading_date, timeframe=timeframe, as_of=as_of,
            )["complete_closed_starts"])
            if timeframe != "1d" else frozenset()
        )
        web_rows = [
            (datetime.fromisoformat(item["start_at"]).astimezone(IST), item)
            for item in websocket
            if item["start_at"] in certified_websocket_starts
        ]
        by_start = {stamp: ("HISTORICAL_CACHE", row) for stamp, row in historical}
        for stamp, row in web_rows:
            by_start.setdefault(stamp, ("LIVE_WEBSOCKET", row))
        candidate = by_start.get(effective_required_at)
        if candidate is None:
            required_identity = effective_required_at.isoformat()
            return Task9ComposedTimeframeEvidenceV1(
                market, timeframe, 1, 0, (), required_identity, None,
                (required_identity,), False, "TIMEFRAME_UNAVAILABLE",
            )
        source, _ = candidate
        required_identity = effective_required_at.isoformat()
        return Task9ComposedTimeframeEvidenceV1(
            market, timeframe, 1, 1, (source,), required_identity,
            required_identity, (), True, None,
        )

    def compose_required(self, *, market, trading_date, as_of, historical_rows_by_timeframe):
        return {timeframe: self.compose(market=market, trading_date=trading_date, timeframe=timeframe, as_of=as_of, historical_rows=historical_rows_by_timeframe.get(timeframe, ())) for timeframe in REQUIRED_TIMEFRAMES}


def build_task9_precomposed_timeframe_provider(*, live_stream_root):
    """Return the Task9-only zero-REST capture provider factory."""
    def factory(data_service):
        cache = getattr(data_service, "cache", None)
        if not callable(getattr(cache, "get_incremental_candidate", None)):
            raise TypeError("Task9 fallback requires cache-only reader")
        adapter = Task9HistoricalWebsocketComposition(live_stream_root=live_stream_root)
        def provider(*, exchange, symboltoken, end_time):
            market = "NIFTY" if (exchange, str(symboltoken)) == ("NSE", "99926000") else "SENSEX" if (exchange, str(symboltoken)) == ("BSE", "99919000") else None
            if market is None: raise ValueError("TASK9_LOCAL_EVIDENCE_UNAVAILABLE_IDENTITY")
            rows, metadata = {}, {}
            for timeframe in REQUIRED_TIMEFRAMES:
                cached = cache.get_incremental_candidate(exchange, symboltoken, timeframe)
                historical = tuple(cached["response"].get("data", ())) if cached else ()
                evidence = adapter.compose(market=market, trading_date=end_time.astimezone(IST).date(), timeframe=timeframe, as_of=end_time, historical_rows=historical)
                if not evidence.ready:
                    if timeframe == "5m":
                        raise ValueError(f"TASK9_LOCAL_EVIDENCE_UNAVAILABLE_{market}_{timeframe}")
                    metadata[timeframe] = {
                        "captured": False, "source": (), "local_composed": True,
                        "warning": f"optional_timeframe_unavailable_{timeframe}",
                        "failure_reason": evidence.failure_reason,
                    }
                    continue
                websocket = () if timeframe == "1d" else adapter.aggregator.candles(market=market, trading_date=end_time.astimezone(IST).date(), timeframe=timeframe, as_of=end_time)
                merged = {datetime.fromisoformat(item[0]).astimezone(IST): tuple(item) for item in historical}
                for item in websocket:
                    merged.setdefault(datetime.fromisoformat(item["start_at"]).astimezone(IST), (item["start_at"], item["open"], item["high"], item["low"], item["close"], 0))
                rows[timeframe] = tuple(row for _, row in sorted(merged.items()))
                metadata[timeframe] = {"captured": True, "source": evidence.source_composition, "local_composed": True}
            return {"rows_by_timeframe": rows, "dataframes": {}, "cache_metadata": metadata, "request_diagnostics": {}}
        return provider
    return factory
