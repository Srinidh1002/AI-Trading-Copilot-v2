"""PAPER-only Task 9 live WebSocket tick journal and closed-candle authority."""
from __future__ import annotations

import json
import os
import threading
import time as wall_time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from services.contracts.task9_collector_observability_v1 import (
    Task9CollectorEventType,
    Task9CollectorEventV1,
    Task9CollectorRunSummaryV1,
)
from services.contracts.task9_market_session_policy_v1 import Task9MarketSegment, Task9SessionPhase


IST = ZoneInfo("Asia/Kolkata")
SOURCE = "LIVE_WEBSOCKET"
TIMEFRAMES = {"5m": 5, "15m": 15, "1h": 60}
MARKETS = {
    ("NSE", "99926000"): {"market": "NIFTY", "exchange_type": 1},
    ("BSE", "99919000"): {"market": "SENSEX", "exchange_type": 3},
}
_SEGMENTS={"NIFTY":Task9MarketSegment.NFO_OPTIONS,"SENSEX":Task9MarketSegment.BFO_OPTIONS}

def task9_tick_stream_session_active(*, market, state, market_date=None):
    """Fail-closed canonical Task 9 monitoring gate; readiness booleans never enter."""
    if market not in _SEGMENTS or state is None or getattr(state,"segment",None) is not _SEGMENTS[market]: return False
    if market_date is not None and getattr(state,"market_date",None)!=market_date:return False
    return getattr(state,"phase",None) in {Task9SessionPhase.OPEN,Task9SessionPhase.ENTRY_RESTRICTED}


class Task9LiveTickError(ValueError):
    """Raised when WebSocket market evidence is malformed or unsafe."""


@dataclass(frozen=True, slots=True)
class Task9LiveTickV1:
    market: str
    exchange: str
    symbol_token: str
    provider_timestamp: datetime
    received_at: datetime
    ltp: float
    source: str = SOURCE

    volume: int | None = None
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    close_price: float | None = None
    open_interest: int | None = None
    subscription_mode: int | str | None = None

    def __post_init__(self):
        identity = (
            self.exchange,
            self.symbol_token,
        )

        if (
            identity not in MARKETS
            or self.market
            != MARKETS[identity]["market"]
        ):
            raise Task9LiveTickError(
                "unsupported Task9 tick identity"
            )

        if (
            self.source != SOURCE
            or self.ltp <= 0
        ):
            raise Task9LiveTickError(
                "invalid Task9 tick"
            )

        for value in (
            self.provider_timestamp,
            self.received_at,
        ):
            if (
                value.tzinfo is None
                or value.utcoffset() is None
            ):
                raise Task9LiveTickError(
                    "tick timestamp must be aware"
                )

        for name in (
            "volume",
            "open_interest",
        ):
            value = getattr(
                self,
                name,
            )

            if (
                value is not None
                and (
                    type(value) is not int
                    or value < 0
                )
            ):
                raise Task9LiveTickError(
                    name
                )

        for name in (
            "open_price",
            "high_price",
            "low_price",
            "close_price",
        ):
            value = getattr(
                self,
                name,
            )

            if (
                value is not None
                and (
                    type(value)
                    not in {int, float}
                    or value <= 0
                )
            ):
                raise Task9LiveTickError(
                    name
                )

        if (
            self.subscription_mode
            is not None
            and (
                type(self.subscription_mode)
                not in {int, str}
                or (
                    type(self.subscription_mode)
                    is str
                    and not self.subscription_mode.strip()
                )
            )
        ):
            raise Task9LiveTickError(
                "subscription_mode"
            )


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"), allow_nan=False)
            handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise Task9LiveTickError(name)
    return value.astimezone(IST)


def _tick_from_dict(
    value: object,
) -> Task9LiveTickV1:
    required = {
        "market",
        "exchange",
        "symbol_token",
        "provider_timestamp",
        "received_at",
        "ltp",
        "source",
    }

    optional = {
        "volume",
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "open_interest",
        "subscription_mode",
    }

    if (
        type(value) is not dict
        or not required.issubset(value)
        or set(value) - required - optional
    ):
        raise Task9LiveTickError(
            "invalid persisted tick"
        )

    try:
        return Task9LiveTickV1(
            market=value["market"],
            exchange=value["exchange"],
            symbol_token=value[
                "symbol_token"
            ],
            provider_timestamp=(
                datetime.fromisoformat(
                    value[
                        "provider_timestamp"
                    ]
                )
            ),
            received_at=(
                datetime.fromisoformat(
                    value["received_at"]
                )
            ),
            ltp=float(value["ltp"]),
            source=value["source"],
            volume=value.get("volume"),
            open_price=value.get(
                "open_price"
            ),
            high_price=value.get(
                "high_price"
            ),
            low_price=value.get(
                "low_price"
            ),
            close_price=value.get(
                "close_price"
            ),
            open_interest=value.get(
                "open_interest"
            ),
            subscription_mode=value.get(
                "subscription_mode"
            ),
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise Task9LiveTickError(
            "invalid persisted tick"
        ) from exc


def normalize_task9_websocket_tick(
    *,
    exchange: str,
    symbol_token: str,
    provider_timestamp: datetime,
    received_at: datetime,
    ltp: object,
    volume=None,
    open_price=None,
    high_price=None,
    low_price=None,
    close_price=None,
    open_interest=None,
    subscription_mode=None,
) -> Task9LiveTickV1:
    identity = (
        str(exchange).strip().upper(),
        str(symbol_token).strip(),
    )

    if identity not in MARKETS:
        raise Task9LiveTickError(
            "unsupported Task9 tick identity"
        )

    try:
        price = float(ltp)
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise Task9LiveTickError(
            "ltp"
        ) from exc

    def optional_integer(
        value,
        name,
    ):
        if value is None:
            return None

        if type(value) is bool:
            raise Task9LiveTickError(
                name
            )

        try:
            numeric = int(value)
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise Task9LiveTickError(
                name
            ) from exc

        if numeric < 0:
            raise Task9LiveTickError(
                name
            )

        return numeric

    def optional_price(
        value,
        name,
    ):
        if value is None:
            return None

        try:
            numeric = float(value)
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise Task9LiveTickError(
                name
            ) from exc

        if numeric <= 0:
            raise Task9LiveTickError(
                name
            )

        return numeric

    return Task9LiveTickV1(
        market=MARKETS[
            identity
        ]["market"],
        exchange=identity[0],
        symbol_token=identity[1],
        provider_timestamp=_aware(
            provider_timestamp,
            "provider_timestamp",
        ),
        received_at=_aware(
            received_at,
            "received_at",
        ),
        ltp=price,
        volume=optional_integer(
            volume,
            "volume",
        ),
        open_price=optional_price(
            open_price,
            "open_price",
        ),
        high_price=optional_price(
            high_price,
            "high_price",
        ),
        low_price=optional_price(
            low_price,
            "low_price",
        ),
        close_price=optional_price(
            close_price,
            "close_price",
        ),
        open_interest=optional_integer(
            open_interest,
            "open_interest",
        ),
        subscription_mode=(
            subscription_mode
        ),
    )


class Task9LiveTickJournal:
    """Legacy-readable append-only raw tick persistence; never performs network work."""
    SCHEMA_VERSION = 1

    def __init__(self, root, *, session_state_resolver=None):
        self.root = Path(root)
        self.session_state_resolver = session_state_resolver
        # Collector-only, seeded once per day. Readers retain disk authority.
        self._append_state: dict[object, dict[str, object]] = {}

    def _path(self, trading_date): return self.root / f"ticks-{trading_date.isoformat()}.json"
    def _jsonl_path(self, trading_date): return self.root / f"ticks-{trading_date.isoformat()}.jsonl"

    @staticmethod
    def _identity(tick):
        return (tick.exchange, tick.symbol_token, tick.provider_timestamp, tick.ltp)

    @staticmethod
    def _serialize(tick):
        return {**asdict(tick), "provider_timestamp": tick.provider_timestamp.isoformat(), "received_at": tick.received_at.isoformat()}

    def _load_legacy(self, trading_date) -> tuple[Task9LiveTickV1, ...]:
        path = self._path(trading_date)
        if not path.exists(): return ()
        try: raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc: raise Task9LiveTickError("tick journal corrupt") from exc
        if type(raw) is not dict or set(raw) != {"schema_version", "trading_date", "ticks"} or raw["schema_version"] != self.SCHEMA_VERSION or raw["trading_date"] != trading_date.isoformat() or type(raw["ticks"]) is not list: raise Task9LiveTickError("tick journal invalid")
        return tuple(_tick_from_dict(item) for item in raw["ticks"])

    def _load_jsonl(self, trading_date) -> tuple[Task9LiveTickV1, ...]:
        path = self._jsonl_path(trading_date)
        if not path.exists(): return ()
        try: raw = path.read_text(encoding="utf-8")
        except OSError as exc: raise Task9LiveTickError("tick journal corrupt") from exc
        # A concurrent reader ignores only an unfinished trailing append.
        lines = raw.splitlines()
        if raw and not raw.endswith("\n"):
            lines = lines[:-1]
        ticks = []
        for line in lines:
            if not line: continue
            try: value = json.loads(line)
            except json.JSONDecodeError as exc: raise Task9LiveTickError("tick journal corrupt") from exc
            ticks.append(_tick_from_dict(value))
        return tuple(ticks)

    def load(self, trading_date) -> tuple[Task9LiveTickV1, ...]:
        source_ticks = self._load_legacy(trading_date) + self._load_jsonl(trading_date)
        latest = {"NIFTY": None, "SENSEX": None}
        unique = {}
        for tick in source_ticks:
            previous = latest[tick.market]
            if previous is not None and tick.provider_timestamp < previous: raise Task9LiveTickError("tick journal order")
            latest[tick.market] = tick.provider_timestamp
            unique.setdefault(self._identity(tick), tick)
        ticks = tuple(sorted(unique.values(), key=lambda item: (item.provider_timestamp, item.received_at, item.market)))
        return ticks

    def _state(self, trading_date):
        state = self._append_state.get(trading_date)
        if state is not None: return state
        ticks = self.load(trading_date)
        state = {"seen": {self._identity(tick) for tick in ticks}, "latest": {market: max((tick.provider_timestamp for tick in ticks if tick.market == market), default=None) for market in ("NIFTY", "SENSEX")}}
        self._append_state[trading_date] = state
        return state

    @staticmethod
    def _discard_incomplete_jsonl_tail(path: Path) -> None:
        """Remove only a crash-interrupted final record before a new append."""
        if not path.exists() or path.stat().st_size == 0:
            return
        with path.open("rb+") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 8192))
            tail = handle.read()
            if tail.endswith(b"\n"):
                return
            boundary = tail.rfind(b"\n")
            if boundary < 0:
                raise Task9LiveTickError("tick journal corrupt")
            handle.truncate(max(0, size - len(tail)) + boundary + 1)

    def append(self, tick: Task9LiveTickV1) -> bool:
        local = tick.provider_timestamp.astimezone(IST)
        state = self.session_state_resolver(market=tick.market, evaluated_at=local, market_date=local.date()) if self.session_state_resolver else None
        if not task9_tick_stream_session_active(market=tick.market,state=state,market_date=local.date()):
            raise Task9LiveTickError("tick outside Task9 parent evidence session")
        day = local.date(); state = self._state(day); identity = self._identity(tick)
        if identity in state["seen"]: return False
        latest = state["latest"][tick.market]
        if latest is not None and tick.provider_timestamp < latest: raise Task9LiveTickError("out-of-order tick")
        path = self._jsonl_path(day); path.parent.mkdir(parents=True, exist_ok=True)
        self._discard_incomplete_jsonl_tail(path)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(self._serialize(tick), sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
            handle.flush()
        state["seen"].add(identity); state["latest"][tick.market] = tick.provider_timestamp
        return True


class Task9LiveCandleAggregator:
    """Deterministic IST-session aggregation; only complete closed windows qualify."""
    def __init__(self, journal: Task9LiveTickJournal): self.journal = journal
    def _resolve_session_state(self, *, market: str, evaluated_at: datetime, market_date):
        resolver = self.journal.session_state_resolver
        if resolver is None:
            return None
        local = _aware(evaluated_at, "evaluated_at")
        state = resolver(
            market=market,
            evaluated_at=local,
            market_date=market_date,
        )
        if not task9_tick_stream_session_active(
            market=market,
            state=state,
            market_date=market_date,
        ):
            return None
        return state

    def _bucket(
        self,
        *,
        market: str,
        timestamp: datetime,
        minutes: int,
    ) -> datetime | None:
        local = timestamp.astimezone(IST)
        state = self._resolve_session_state(
            market=market,
            evaluated_at=local,
            market_date=local.date(),
        )
        if state is None:
            return None

        start = datetime.combine(
            local.date(),
            state.session_open_time,
            IST,
        )
        close = datetime.combine(
            local.date(),
            state.session_close_time,
            IST,
        )

        if not start <= local < close:
            return None

        offset = int((local - start).total_seconds() // 60)
        bucket = start + timedelta(
            minutes=(offset // minutes) * minutes
        )
        return (
            bucket
            if bucket + timedelta(minutes=minutes) <= close
            else None
        )

    def _closed_starts(
        self,
        *,
        market: str,
        trading_date,
        timeframe: str,
        as_of: datetime,
    ) -> tuple[datetime, ...]:
        minutes = TIMEFRAMES[timeframe]
        cutoff = _aware(as_of, "as_of")
        state = self._resolve_session_state(
            market=market,
            evaluated_at=cutoff,
            market_date=trading_date,
        )
        if state is None:
            return ()

        session_start = datetime.combine(
            trading_date,
            state.session_open_time,
            IST,
        )
        session_close = datetime.combine(
            trading_date,
            state.session_close_time,
            IST,
        )
        session_end = min(session_close, cutoff)

        starts = []
        while session_start + timedelta(minutes=minutes) <= session_end:
            starts.append(session_start)
            session_start += timedelta(minutes=minutes)
        return tuple(starts)

    def _certified_closed_starts(self, *, market: str, trading_date, timeframe: str, as_of: datetime) -> tuple[datetime, ...]:
        """Return closed windows whose raw capture demonstrably started in time."""
        ticks = tuple(tick for tick in self.journal.load(trading_date) if tick.market == market)
        observed = {
            self._bucket(
                market=market,
                timestamp=tick.provider_timestamp,
                minutes=5,
            )
            for tick in ticks
        }
        observed.discard(None)
        if not observed:
            return ()
        earliest_capture = min(tick.provider_timestamp.astimezone(IST) for tick in ticks)
        minutes = TIMEFRAMES[timeframe]
        return tuple(
            start
            for start in self._closed_starts(
                market=market,
                trading_date=trading_date,
                timeframe=timeframe,
                as_of=as_of,
            )
            if earliest_capture <= start
            and all(start + timedelta(minutes=step) in observed for step in range(0, minutes, 5))
        )

    def candles(self, *, market: str, trading_date, timeframe: str, as_of: datetime) -> tuple[dict[str, object], ...]:
        if timeframe not in TIMEFRAMES or market not in {"NIFTY", "SENSEX"}: raise Task9LiveTickError("candle identity")
        resolver=self.journal.session_state_resolver; state=resolver(market=market,evaluated_at=_aware(as_of,"as_of"),market_date=trading_date) if resolver else None
        if not task9_tick_stream_session_active(market=market,state=state,market_date=trading_date): return ()
        minutes = TIMEFRAMES[timeframe]; cutoff = _aware(as_of, "as_of")
        certified = set(self._certified_closed_starts(market=market, trading_date=trading_date, timeframe=timeframe, as_of=cutoff))
        groups: dict[datetime, list[Task9LiveTickV1]] = {}
        for tick in self.journal.load(trading_date):
            if tick.market != market: continue
            bucket = self._bucket(
                market=market,
                timestamp=tick.provider_timestamp,
                minutes=minutes,
            )
            if bucket in certified and bucket + timedelta(minutes=minutes) <= cutoff: groups.setdefault(bucket, []).append(tick)
        return tuple({"market": market, "timeframe": timeframe, "start_at": start.isoformat(), "end_at": (start + timedelta(minutes=minutes)).isoformat(), "open": values[0].ltp, "high": max(item.ltp for item in values), "low": min(item.ltp for item in values), "close": values[-1].ltp, "source": SOURCE} for start, values in sorted(groups.items()))
    def coverage(self, *, market: str, trading_date, timeframe: str, as_of: datetime) -> dict[str, object]:
        if timeframe not in TIMEFRAMES or market not in {"NIFTY", "SENSEX"}: raise Task9LiveTickError("candle identity")
        required = self._closed_starts(
            market=market,
            trading_date=trading_date,
            timeframe=timeframe,
            as_of=as_of,
        )
        complete = self._certified_closed_starts(market=market, trading_date=trading_date, timeframe=timeframe, as_of=as_of)
        observed = {
            self._bucket(
                market=market,
                timestamp=tick.provider_timestamp,
                minutes=5,
            )
            for tick in self.journal.load(trading_date)
            if tick.market == market
        }
        observed.discard(None)
        earliest = min(observed).isoformat() if observed else None
        return {"market": market, "timeframe": timeframe, "earliest_observed_at": earliest, "complete_closed_starts": tuple(item.isoformat() for item in complete), "missing_closed_starts": tuple(item.isoformat() for item in required if item not in complete), "source": SOURCE}


class Task9LiveTickStream:
    """One shared official-SDK connection; it only journals subscribed spot ticks."""

    RECONNECT_DELAYS_SECONDS = (
        2.0,
        5.0,
        15.0,
        30.0,
    )

    STALE_TICK_SECONDS = 30.0
    PROVIDER_LAG_SECONDS = 30.0
    EVENT_HISTORY_LIMIT = 128

    def __init__(
        self,
        *,
        journal: Task9LiveTickJournal,
        websocket_factory,
        credentials,
        collector_run_id=None,
        event_sink=None,
    ):
        self.journal = journal
        self.websocket_factory = websocket_factory
        self.credentials = credentials
        self.websocket = None

        self.events = deque(
            maxlen=self.EVENT_HISTORY_LIMIT
        )

        # Compatibility projections retained for existing diagnostics.
        self.last_valid_tick_received_at: datetime | None = None
        self.last_callback_received_at: datetime | None = None
        self.latest_provider_timestamp: datetime | None = None

        # Canonical runtime freshness authority is market-specific.
        self.last_valid_tick_received_at_by_market = {
            "NIFTY": None,
            "SENSEX": None,
        }

        self.latest_provider_timestamp_by_market = {
            "NIFTY": None,
            "SENSEX": None,
        }

        self._session_opened_at: datetime | None = None
        self._stop_requested = threading.Event()
        self._session_open = False
        self._healthy_session = False
        self._stale_reconnect_requested = False
        self._lagging_backlog_reported = False

        if (
            collector_run_id is None
        ) != (
            event_sink is None
        ):
            raise ValueError(
                "collector event authority incomplete"
            )

        self.collector_run_id = (
            collector_run_id
        )

        self.event_sink = (
            event_sink
        )

        self._canonical_event_sequence = 0
        self._canonical_event_ids = []
        self._ever_connected = False
        self.connected_at = None
        self.reconnect_count = 0
        self.close_reason = "UNRESOLVED"
        self.session_close_state = (
            "NOT_REACHED"
        )

    def _event(
        self,
        state: str,
        *,
        canonical_type=None,
        market=None,
        observed_at=None,
        detail_code=None,
        retain_legacy=True,
    ) -> None:
        """Retain legacy state plus optional durable canonical evidence."""

        if retain_legacy:
            self.events.append(
                state
            )

        if canonical_type is None:
            return

        if self.event_sink is None:
            return

        observed = _aware(
            observed_at
            or datetime.now(IST),
            "event observed_at",
        )

        self._canonical_event_sequence += 1

        event_type = (
            Task9CollectorEventType(
                canonical_type
            )
        )

        event_id = (
            f"{self.collector_run_id}:"
            f"{self._canonical_event_sequence:08d}:"
            f"{event_type.value}"
        )

        event = Task9CollectorEventV1(
            event_id=event_id,
            collector_run_id=(
                self.collector_run_id
            ),
            event_type=event_type,
            observed_at=observed,
            market=market,
            detail_code=detail_code,
        )

        self.event_sink(
            event
        )

        self._canonical_event_ids.append(
            event.event_id
        )

    @staticmethod
    def subscriptions():
        return [
            {
                "exchangeType": value["exchange_type"],
                "tokens": [token],
            }
            for (
                exchange,
                token,
            ), value in MARKETS.items()
        ]

    def _prepare_session(self):
        """Create one fresh socket and attach its Task9-only callbacks."""

        self.websocket = self.websocket_factory(
            **self.credentials
        )

        self.websocket.on_open = self._on_open
        self.websocket.on_data = self._on_data
        self.websocket.on_error = self._on_error
        self.websocket.on_close = self._on_close

        self._session_open = False
        self._healthy_session = False
        self._stale_reconnect_requested = False
        self._lagging_backlog_reported = False

        # Connection/session-local compatibility state resets here.
        self.last_valid_tick_received_at = None
        self.last_callback_received_at = None
        self.latest_provider_timestamp = None

        # Per-market state is also connection-local. Durable journal facts
        # remain available independently to startup/readiness authorities.
        self.last_valid_tick_received_at_by_market = {
            "NIFTY": None,
            "SENSEX": None,
        }

        self.latest_provider_timestamp_by_market = {
            "NIFTY": None,
            "SENSEX": None,
        }

        self._session_opened_at = None
        self._event("CONNECTING")

    def start(self):
        """Run one blocking SDK socket session."""

        self._prepare_session()
        return self.websocket.connect()

    def _connect_prepared_session(
        self,
    ) -> None:
        try:
            self.websocket.connect()
        except Exception:
            # Transport failures are retried by this supervisor only.
            # Never retain provider exception text because it may contain
            # sensitive transport/session material.
            self._on_error()

    def _on_open(
        self,
        *_,
    ):
        self._session_open = True
        self._session_opened_at = (
            datetime.now(IST)
        )

        if self.connected_at is None:
            self.connected_at = (
                self._session_opened_at
            )

        self._event(
            "OPEN",
            canonical_type=(
                Task9CollectorEventType.RECONNECTED
                if self._ever_connected
                else Task9CollectorEventType.CONNECTED
            ),
            observed_at=(
                self._session_opened_at
            ),
        )

        self._ever_connected = True

        self.websocket.subscribe(
            "task9-live-candles",
            1,
            self.subscriptions(),
        )

        self._event(
            "SUBSCRIBED",
            canonical_type=(
                Task9CollectorEventType.SUBSCRIBED
            ),
            observed_at=(
                self._session_opened_at
            ),
            retain_legacy=False,
        )

    def _on_error(
        self,
        *_,
    ):
        self._session_open = False

        self._event(
            "ERROR",
            canonical_type=(
                Task9CollectorEventType.PROVIDER_ERROR
            ),
            detail_code=(
                "WEBSOCKET_PROVIDER_ERROR"
            ),
        )

    def _on_close(
        self,
        *_,
    ):
        self._session_open = False

        self._event(
            "CLOSED",
            canonical_type=(
                Task9CollectorEventType.DISCONNECTED
            ),
        )

    def _market_session_open(
        self,
        value: datetime,
        *,
        market: str | None = None,
    ) -> bool:
        local = _aware(
            value,
            "clock",
        )

        resolver = (
            self.journal.session_state_resolver
        )

        if not callable(resolver):
            return False

        markets = (
            (market,)
            if market is not None
            else ("NIFTY", "SENSEX")
        )

        return any(
            task9_tick_stream_session_active(
                market=item,
                state=resolver(
                    market=item,
                    evaluated_at=local,
                    market_date=local.date(),
                ),
                market_date=local.date(),
            )
            for item in markets
        )

    def _all_market_sessions_terminal(
        self,
        value: datetime,
    ) -> bool:
        """Return True only when both canonical Task 9 markets are terminal."""

        local = _aware(
            value,
            "clock",
        )

        resolver = (
            self.journal.session_state_resolver
        )

        if not callable(resolver):
            return False

        terminal_phases = {
            Task9SessionPhase.CLOSED,
            Task9SessionPhase.NON_TRADING_DAY,
        }

        for market in (
            "NIFTY",
            "SENSEX",
        ):
            state = resolver(
                market=market,
                evaluated_at=local,
                market_date=local.date(),
            )

            if (
                state is None
                or getattr(
                    state,
                    "segment",
                    None,
                )
                is not _SEGMENTS[market]
                or getattr(
                    state,
                    "market_date",
                    None,
                )
                != local.date()
                or getattr(
                    state,
                    "phase",
                    None,
                )
                not in terminal_phases
            ):
                return False

        return True

    def _request_session_close_if_terminal(
        self,
        value: datetime,
    ) -> bool:
        """Stop the collector only after both canonical markets are terminal."""

        if not self._all_market_sessions_terminal(
            value
        ):
            return False

        self.close_reason = "SESSION_CLOSED"
        self.session_close_state = (
            "SESSION_CLOSED"
        )

        self.request_stop()

        return True

    def _market_is_stale(
        self,
        *,
        market: str,
        now: datetime,
    ) -> bool:
        if market not in {
            "NIFTY",
            "SENSEX",
        }:
            raise ValueError("market")

        if (
            not self._session_open
            or not self._market_session_open(
                now,
                market=market,
            )
        ):
            return False

        activity_at = (
            self.last_valid_tick_received_at_by_market[
                market
            ]
            or self._session_opened_at
        )

        if activity_at is None:
            return False

        return (
            now.astimezone(IST)
            - activity_at.astimezone(IST)
        ).total_seconds() > self.STALE_TICK_SECONDS

    def _stale_markets(
        self,
        now: datetime,
    ) -> tuple[str, ...]:
        return tuple(
            market
            for market in (
                "NIFTY",
                "SENSEX",
            )
            if self._market_is_stale(
                market=market,
                now=now,
            )
        )

    def _is_stale(
        self,
        now: datetime,
    ) -> bool:
        """Compatibility projection over canonical per-market freshness."""

        return bool(
            self._stale_markets(now)
        )

    def health(
        self,
        *,
        now=None,
    ) -> dict[str, object]:
        """Expose read-only independent per-market collector health."""

        current = _aware(
            now or datetime.now(IST),
            "clock",
        )

        markets = {}

        any_lagging = False
        any_stale = False

        for market in (
            "NIFTY",
            "SENSEX",
        ):
            received_at = (
                self.last_valid_tick_received_at_by_market[
                    market
                ]
            )

            provider_timestamp = (
                self.latest_provider_timestamp_by_market[
                    market
                ]
            )

            session_open = (
                self._session_open
                and self._market_session_open(
                    current,
                    market=market,
                )
            )

            stale = self._market_is_stale(
                market=market,
                now=current,
            )

            lagging = (
                session_open
                and provider_timestamp is not None
                and (
                    current
                    - provider_timestamp.astimezone(IST)
                ).total_seconds()
                > self.PROVIDER_LAG_SECONDS
            )

            any_stale = (
                any_stale
                or stale
            )

            any_lagging = (
                any_lagging
                or lagging
            )

            markets[market] = {
                "state": (
                    "STALE"
                    if stale
                    else (
                        "LAGGING_BACKLOG"
                        if lagging
                        else (
                            "OPEN"
                            if session_open
                            else "CLOSED"
                        )
                    )
                ),
                "last_valid_tick_received_at": (
                    received_at.isoformat()
                    if received_at
                    else None
                ),
                "latest_provider_timestamp": (
                    provider_timestamp.isoformat()
                    if provider_timestamp
                    else None
                ),
                "provider_timestamp_authority": True,
            }

        # Preserve the old top-level health surface for compatibility.
        compatibility_lagging = (
            self._session_open
            and self.latest_provider_timestamp
            is not None
            and (
                current
                - self.latest_provider_timestamp.astimezone(IST)
            ).total_seconds()
            > self.PROVIDER_LAG_SECONDS
        )

        state = (
            "STALE"
            if any_stale
            else (
                "LAGGING_BACKLOG"
                if any_lagging
                or compatibility_lagging
                else (
                    "OPEN"
                    if self._session_open
                    else "CLOSED"
                )
            )
        )

        return {
            "state": state,
            "last_callback_received_at": (
                self.last_callback_received_at.isoformat()
                if self.last_callback_received_at
                else None
            ),
            "latest_provider_timestamp": (
                self.latest_provider_timestamp.isoformat()
                if self.latest_provider_timestamp
                else None
            ),
            "provider_timestamp_authority": True,
            "markets": markets,
        }

    def request_stop(
        self,
    ) -> None:
        """Stop supervision and safely close only the current socket."""

        self._stop_requested.set()

        socket = self.websocket

        if (
            socket is not None
            and callable(
                getattr(
                    socket,
                    "close_connection",
                    None,
                )
            )
        ):
            socket.close_connection()

    def run_forever(
        self,
        *,
        clock=None,
        sleep=None,
        poll_interval_seconds=0.25,
        wait_for_stop=None,
        max_sessions=None,
    ) -> None:
        """Supervise sequential blocking SDK sessions until explicitly stopped."""

        if poll_interval_seconds <= 0:
            raise ValueError(
                "poll_interval_seconds"
            )

        if (
            max_sessions is not None
            and (
                type(max_sessions) is not int
                or max_sessions <= 0
            )
        ):
            raise ValueError(
                "max_sessions"
            )

        clock = (
            clock
            or (
                lambda: datetime.now(IST)
            )
        )

        sleep = (
            sleep
            or wall_time.sleep
        )

        wait_for_stop = (
            wait_for_stop
            or self._stop_requested.wait
        )

        backoff_index = 0
        sessions_started = 0

        self._stop_requested.clear()

        try:
            while not self._stop_requested.is_set():
                current = _aware(
                    clock(),
                    "clock",
                )

                if self._request_session_close_if_terminal(
                    current
                ):
                    break

                self._prepare_session()

                session = threading.Thread(
                    target=self._connect_prepared_session,
                    name="task9-live-websocket",
                    daemon=True,
                )

                session.start()
                sessions_started += 1

                while (
                    session.is_alive()
                    and not self._stop_requested.is_set()
                ):
                    current = _aware(
                        clock(),
                        "clock",
                    )

                    if self._request_session_close_if_terminal(
                        current
                    ):
                        break

                    stale_markets = (
                        self._stale_markets(
                            current
                        )
                    )

                    if (
                        stale_markets
                        and not self._stale_reconnect_requested
                    ):
                        for _market in stale_markets:
                            never_received = (
                                self.last_valid_tick_received_at_by_market[
                                    _market
                                ]
                                is None
                            )

                            event_type = (
                                Task9CollectorEventType.NO_TICK
                                if never_received
                                else Task9CollectorEventType.STALE
                            )

                            self._event(
                                f"STALE:{_market}",
                                canonical_type=event_type,
                                market=_market,
                                observed_at=current,
                                detail_code=(
                                    "NO_VALID_MARKET_TICK"
                                    if never_received
                                    else "MARKET_TICK_STALE"
                                ),
                            )

                        # Legacy generic event remains available.
                        self._event("STALE")

                        self._stale_reconnect_requested = True

                        socket = self.websocket

                        if (
                            socket is not None
                            and callable(
                                getattr(
                                    socket,
                                    "close_connection",
                                    None,
                                )
                            )
                        ):
                            socket.close_connection()

                    sleep(
                        poll_interval_seconds
                    )

                if self._stop_requested.is_set():
                    self.request_stop()
                    session.join(
                        timeout=5.0
                    )
                    break

                session.join()

                current = _aware(
                    clock(),
                    "clock",
                )

                if self._request_session_close_if_terminal(
                    current
                ):
                    break

                if (
                    max_sessions is not None
                    and sessions_started
                    >= max_sessions
                ):
                    break

                delay = (
                    self.RECONNECT_DELAYS_SECONDS[
                        backoff_index
                    ]
                )

                backoff_index = (
                    0
                    if self._healthy_session
                    else min(
                        backoff_index + 1,
                        len(
                            self.RECONNECT_DELAYS_SECONDS
                        )
                        - 1,
                    )
                )

                self.reconnect_count += 1

                self._event(
                    "RECONNECTING",
                    canonical_type=(
                        Task9CollectorEventType.RECONNECTING
                    ),
                )

                if wait_for_stop(
                    delay
                ):
                    break

        finally:
            if self.close_reason == "UNRESOLVED":
                self.close_reason = (
                    "STOP_REQUESTED"
                    if self._stop_requested.is_set()
                    else "SUPERVISOR_EXIT"
                )

            self.request_stop()

            self._event(
                "STOPPED",
                canonical_type=(
                    Task9CollectorEventType.STOPPED
                ),
            )

    def build_run_summary(
        self,
        *,
        started_at: datetime,
        stopped_at: datetime,
    ) -> Task9CollectorRunSummaryV1:
        return Task9CollectorRunSummaryV1(
            collector_run_id=(
                self.collector_run_id
                or "task9-collector-untracked"
            ),
            started_at=_aware(
                started_at,
                "started_at",
            ),
            stopped_at=_aware(
                stopped_at,
                "stopped_at",
            ),
            connected_at=(
                self.connected_at
            ),
            markets_subscribed=(
                "NIFTY",
                "SENSEX",
            ),
            nifty_last_tick_received_at=(
                self.last_valid_tick_received_at_by_market[
                    "NIFTY"
                ]
            ),
            sensex_last_tick_received_at=(
                self.last_valid_tick_received_at_by_market[
                    "SENSEX"
                ]
            ),
            reconnect_count=(
                self.reconnect_count
            ),
            event_ids=tuple(
                self._canonical_event_ids
            ),
            close_reason=(
                self.close_reason
            ),
            session_close_state=(
                self.session_close_state
            ),
        )

    def _on_data(
        self,
        _,
        message,
    ):
        received_at = datetime.now(IST)

        # Compatibility timestamp means any SDK callback.
        self.last_callback_received_at = (
            received_at
        )

        try:
            exchange_type = message.get(
                "exchange_type"
            )

            identity = next(
                (
                    key
                    for key, value
                    in MARKETS.items()
                    if (
                        value["exchange_type"]
                        == exchange_type
                        and key[1]
                        == str(
                            message.get(
                                "token"
                            )
                        )
                    )
                ),
                None,
            )

            if identity is None:
                raise Task9LiveTickError(
                    "unsupported websocket tick"
                )

            timestamp = (
                message.get(
                    "exchange_timestamp"
                )
                or message.get(
                    "last_traded_timestamp"
                )
            )

            if isinstance(
                timestamp,
                (int, float),
            ):
                timestamp = (
                    datetime.fromtimestamp(
                        timestamp / 1000,
                        IST,
                    )
                )

            if not isinstance(
                timestamp,
                datetime,
            ):
                raise Task9LiveTickError(
                    "provider_timestamp"
                )

            price = message.get(
                "last_traded_price"
            )

            if isinstance(
                price,
                int,
            ):
                price = (
                    price / 100
                )

            def provider_price(
                key,
            ):
                value = message.get(
                    key
                )

                if value is None:
                    return None

                if isinstance(
                    value,
                    int,
                ):
                    return (
                        value / 100
                    )

                return value

            tick = (
                normalize_task9_websocket_tick(
                    exchange=identity[0],
                    symbol_token=identity[1],
                    provider_timestamp=timestamp,
                    received_at=received_at,
                    ltp=price,
                    volume=message.get(
                        "volume_trade_for_the_day"
                    ),
                    open_price=provider_price(
                        "open_price_of_the_day"
                    ),
                    high_price=provider_price(
                        "high_price_of_the_day"
                    ),
                    low_price=provider_price(
                        "low_price_of_the_day"
                    ),
                    close_price=provider_price(
                        "closed_price"
                    ),
                    open_interest=message.get(
                        "open_interest"
                    ),
                    subscription_mode=message.get(
                        "subscription_mode"
                    ),
                )
            )

            self.journal.append(
                tick
            )

            market = tick.market

            self.last_valid_tick_received_at_by_market[
                market
            ] = received_at

            self.latest_provider_timestamp_by_market[
                market
            ] = tick.provider_timestamp

            # Compatibility projections: latest accepted tick of either market.
            self.last_valid_tick_received_at = (
                received_at
            )

            self.latest_provider_timestamp = (
                tick.provider_timestamp
            )

            self._healthy_session = True

            if (
                self.health(
                    now=received_at
                )["state"]
                == "LAGGING_BACKLOG"
                and not self._lagging_backlog_reported
            ):
                self._event(
                    "LAGGING_BACKLOG"
                )

                self._lagging_backlog_reported = True

        except Task9LiveTickError as exc:
            reason = str(exc)

            dropped = (
                reason
                == "unsupported websocket tick"
            )

            self._event(
                "REJECTED_TICK",
                canonical_type=(
                    Task9CollectorEventType.DROPPED_MESSAGE
                    if dropped
                    else Task9CollectorEventType.PARSE_ERROR
                ),
                detail_code=(
                    "UNSUPPORTED_MESSAGE_IDENTITY"
                    if dropped
                    else "WEBSOCKET_MESSAGE_INVALID"
                ),
                observed_at=received_at,
            )
