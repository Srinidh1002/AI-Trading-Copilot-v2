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

from services.bse_holiday_calendar import get_bse_holiday_calendar
from services.nse_holiday_calendar import get_nse_holiday_calendar


IST = ZoneInfo("Asia/Kolkata")
SOURCE = "LIVE_WEBSOCKET"
SESSION_OPEN = time(9, 15)
SESSION_CLOSE = time(15, 30)
TIMEFRAMES = {"5m": 5, "15m": 15, "1h": 60}
MARKETS = {
    ("NSE", "99926000"): {"market": "NIFTY", "exchange_type": 1},
    ("BSE", "99919000"): {"market": "SENSEX", "exchange_type": 3},
}


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

    def __post_init__(self):
        identity = (self.exchange, self.symbol_token)
        if identity not in MARKETS or self.market != MARKETS[identity]["market"]:
            raise Task9LiveTickError("unsupported Task9 tick identity")
        if self.source != SOURCE or self.ltp <= 0:
            raise Task9LiveTickError("invalid Task9 tick")
        for value in (self.provider_timestamp, self.received_at):
            if value.tzinfo is None or value.utcoffset() is None:
                raise Task9LiveTickError("tick timestamp must be aware")


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


def _tick_from_dict(value: object) -> Task9LiveTickV1:
    if type(value) is not dict or set(value) != {"market", "exchange", "symbol_token", "provider_timestamp", "received_at", "ltp", "source"}:
        raise Task9LiveTickError("invalid persisted tick")
    try:
        return Task9LiveTickV1(
            market=value["market"], exchange=value["exchange"], symbol_token=value["symbol_token"],
            provider_timestamp=datetime.fromisoformat(value["provider_timestamp"]),
            received_at=datetime.fromisoformat(value["received_at"]), ltp=float(value["ltp"]), source=value["source"],
        )
    except (TypeError, ValueError) as exc:
        raise Task9LiveTickError("invalid persisted tick") from exc


def normalize_task9_websocket_tick(*, exchange: str, symbol_token: str, provider_timestamp: datetime, received_at: datetime, ltp: object) -> Task9LiveTickV1:
    identity = (str(exchange).strip().upper(), str(symbol_token).strip())
    if identity not in MARKETS:
        raise Task9LiveTickError("unsupported Task9 tick identity")
    try:
        price = float(ltp)
    except (TypeError, ValueError) as exc:
        raise Task9LiveTickError("ltp") from exc
    return Task9LiveTickV1(MARKETS[identity]["market"], identity[0], identity[1], _aware(provider_timestamp, "provider_timestamp"), _aware(received_at, "received_at"), price)


class Task9LiveTickJournal:
    """Legacy-readable append-only raw tick persistence; never performs network work."""
    SCHEMA_VERSION = 1

    def __init__(self, root):
        self.root = Path(root)
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
        if not SESSION_OPEN <= local.timetz().replace(tzinfo=None) < SESSION_CLOSE:
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
    @staticmethod
    def _bucket(timestamp: datetime, minutes: int) -> datetime | None:
        local = timestamp.astimezone(IST); start = datetime.combine(local.date(), SESSION_OPEN, IST); close = datetime.combine(local.date(), SESSION_CLOSE, IST)
        if not start <= local < close: return None
        offset = int((local - start).total_seconds() // 60); bucket = start + timedelta(minutes=(offset // minutes) * minutes)
        return bucket if bucket + timedelta(minutes=minutes) <= close else None

    def _closed_starts(self, *, trading_date, timeframe: str, as_of: datetime) -> tuple[datetime, ...]:
        minutes = TIMEFRAMES[timeframe]
        cutoff = _aware(as_of, "as_of")
        session_start = datetime.combine(trading_date, SESSION_OPEN, IST)
        session_end = min(datetime.combine(trading_date, SESSION_CLOSE, IST), cutoff)
        starts = []
        while session_start + timedelta(minutes=minutes) <= session_end:
            starts.append(session_start)
            session_start += timedelta(minutes=minutes)
        return tuple(starts)

    def _certified_closed_starts(self, *, market: str, trading_date, timeframe: str, as_of: datetime) -> tuple[datetime, ...]:
        """Return closed windows whose raw capture demonstrably started in time."""
        ticks = tuple(tick for tick in self.journal.load(trading_date) if tick.market == market)
        observed = {self._bucket(tick.provider_timestamp, 5) for tick in ticks}
        observed.discard(None)
        if not observed:
            return ()
        earliest_capture = min(tick.provider_timestamp.astimezone(IST) for tick in ticks)
        minutes = TIMEFRAMES[timeframe]
        return tuple(
            start for start in self._closed_starts(trading_date=trading_date, timeframe=timeframe, as_of=as_of)
            if earliest_capture <= start
            and all(start + timedelta(minutes=step) in observed for step in range(0, minutes, 5))
        )

    def candles(self, *, market: str, trading_date, timeframe: str, as_of: datetime) -> tuple[dict[str, object], ...]:
        if timeframe not in TIMEFRAMES or market not in {"NIFTY", "SENSEX"}: raise Task9LiveTickError("candle identity")
        minutes = TIMEFRAMES[timeframe]; cutoff = _aware(as_of, "as_of")
        certified = set(self._certified_closed_starts(market=market, trading_date=trading_date, timeframe=timeframe, as_of=cutoff))
        groups: dict[datetime, list[Task9LiveTickV1]] = {}
        for tick in self.journal.load(trading_date):
            if tick.market != market: continue
            bucket = self._bucket(tick.provider_timestamp, minutes)
            if bucket in certified and bucket + timedelta(minutes=minutes) <= cutoff: groups.setdefault(bucket, []).append(tick)
        return tuple({"market": market, "timeframe": timeframe, "start_at": start.isoformat(), "end_at": (start + timedelta(minutes=minutes)).isoformat(), "open": values[0].ltp, "high": max(item.ltp for item in values), "low": min(item.ltp for item in values), "close": values[-1].ltp, "source": SOURCE} for start, values in sorted(groups.items()))
    def coverage(self, *, market: str, trading_date, timeframe: str, as_of: datetime) -> dict[str, object]:
        if timeframe not in TIMEFRAMES or market not in {"NIFTY", "SENSEX"}: raise Task9LiveTickError("candle identity")
        required = self._closed_starts(trading_date=trading_date, timeframe=timeframe, as_of=as_of)
        complete = self._certified_closed_starts(market=market, trading_date=trading_date, timeframe=timeframe, as_of=as_of)
        observed = {self._bucket(tick.provider_timestamp, 5) for tick in self.journal.load(trading_date) if tick.market == market}; observed.discard(None)
        earliest = min(observed).isoformat() if observed else None
        return {"market": market, "timeframe": timeframe, "earliest_observed_at": earliest, "complete_closed_starts": tuple(item.isoformat() for item in complete), "missing_closed_starts": tuple(item.isoformat() for item in required if item not in complete), "source": SOURCE}


class Task9LiveTickStream:
    """One shared official-SDK connection; it only journals subscribed spot ticks."""
    RECONNECT_DELAYS_SECONDS = (2.0, 5.0, 15.0, 30.0)
    STALE_TICK_SECONDS = 30.0
    PROVIDER_LAG_SECONDS = 30.0
    EVENT_HISTORY_LIMIT = 128

    def __init__(self, *, journal: Task9LiveTickJournal, websocket_factory, credentials):
        self.journal, self.websocket_factory, self.credentials, self.websocket = journal, websocket_factory, credentials, None
        self.events = deque(maxlen=self.EVENT_HISTORY_LIMIT)
        self.last_valid_tick_received_at: datetime | None = None
        self.last_callback_received_at: datetime | None = None
        self.latest_provider_timestamp: datetime | None = None
        self._session_opened_at: datetime | None = None
        self._stop_requested = threading.Event()
        self._session_open = False
        self._healthy_session = False
        self._stale_reconnect_requested = False
        self._lagging_backlog_reported = False

    def _event(self, state: str) -> None:
        """Retain sanitized bounded lifecycle state only; never credentials."""
        self.events.append(state)
    @staticmethod
    def subscriptions():
        return [{"exchangeType": value["exchange_type"], "tokens": [token]} for (exchange, token), value in MARKETS.items()]
    def _prepare_session(self):
        """Create one fresh socket and attach its Task9-only callbacks."""
        self.websocket = self.websocket_factory(**self.credentials)
        self.websocket.on_open = self._on_open; self.websocket.on_data = self._on_data
        self.websocket.on_error = self._on_error
        self.websocket.on_close = self._on_close
        self._session_open = False
        self._healthy_session = False
        self._stale_reconnect_requested = False
        self._lagging_backlog_reported = False
        self.last_valid_tick_received_at = None
        self.last_callback_received_at = None
        self.latest_provider_timestamp = None
        self._session_opened_at = None
        self._event("CONNECTING")

    def start(self):
        """Run one blocking SDK socket session (the supervisor owns retries)."""
        self._prepare_session()
        return self.websocket.connect()

    def _connect_prepared_session(self) -> None:
        try:
            self.websocket.connect()
        except Exception:
            # Transport failures are retried by the supervisor; no error detail
            # is retained because SDK exceptions can contain sensitive context.
            self._on_error()

    def _on_open(self, *_):
        self._session_open = True
        self._session_opened_at = datetime.now(IST)
        self._event("OPEN")
        # A fresh SDK instance has no subscription state: exactly one call per OPEN.
        self.websocket.subscribe("task9-live-candles", 1, self.subscriptions())

    def _on_error(self, *_):
        self._session_open = False
        self._event("ERROR")

    def _on_close(self, *_):
        self._session_open = False
        self._event("CLOSED")

    @staticmethod
    def _market_session_open(value: datetime) -> bool:
        local = _aware(value, "clock")
        if local.weekday() >= 5 or not SESSION_OPEN <= local.timetz().replace(tzinfo=None) < SESSION_CLOSE:
            return False
        trading_date = local.date()
        return not (
            get_nse_holiday_calendar().is_holiday(trading_date)
            and get_bse_holiday_calendar().is_holiday(trading_date)
        )

    def _is_stale(self, now: datetime) -> bool:
        if not self._session_open or not self._market_session_open(now):
            return False
        activity_at = self.last_callback_received_at or self._session_opened_at
        if activity_at is None:
            return False
        return (now.astimezone(IST) - activity_at).total_seconds() > self.STALE_TICK_SECONDS

    def health(self, *, now=None) -> dict[str, object]:
        """Expose timestamp-separated, read-only collector health evidence."""
        current = _aware(now or datetime.now(IST), "clock")
        lagging = (
            self._session_open
            and self._market_session_open(current)
            and self.latest_provider_timestamp is not None
            and (current - self.latest_provider_timestamp).total_seconds() > self.PROVIDER_LAG_SECONDS
        )
        return {
            "state": "LAGGING_BACKLOG" if lagging else ("OPEN" if self._session_open else "CLOSED"),
            "last_callback_received_at": self.last_callback_received_at.isoformat() if self.last_callback_received_at else None,
            "latest_provider_timestamp": self.latest_provider_timestamp.isoformat() if self.latest_provider_timestamp else None,
            "provider_timestamp_authority": True,
        }

    def request_stop(self) -> None:
        """Stop supervision and safely close only the current socket."""
        self._stop_requested.set()
        socket = self.websocket
        if socket is not None and callable(getattr(socket, "close_connection", None)):
            socket.close_connection()

    def run_forever(self, *, clock=None, sleep=None, poll_interval_seconds=0.25, wait_for_stop=None, max_sessions=None) -> None:
        """Supervise sequential blocking SDK sessions until explicitly stopped."""
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds")
        if max_sessions is not None and (type(max_sessions) is not int or max_sessions <= 0):
            raise ValueError("max_sessions")
        clock = clock or (lambda: datetime.now(IST))
        sleep = sleep or wall_time.sleep
        wait_for_stop = wait_for_stop or self._stop_requested.wait
        backoff_index = 0
        sessions_started = 0
        self._stop_requested.clear()
        try:
            while not self._stop_requested.is_set():
                # SDK connect() blocks; a daemon worker permits stale monitoring and safe close.
                # Construction errors are local/authentication failures and must
                # propagate rather than becoming an uncontrolled retry loop.
                self._prepare_session()
                session = threading.Thread(target=self._connect_prepared_session, name="task9-live-websocket", daemon=True)
                session.start()
                sessions_started += 1
                while session.is_alive() and not self._stop_requested.is_set():
                    if not self._stale_reconnect_requested and self._is_stale(_aware(clock(), "clock")):
                        self._event("STALE")
                        self._stale_reconnect_requested = True
                        socket = self.websocket
                        if socket is not None and callable(getattr(socket, "close_connection", None)):
                            socket.close_connection()
                    sleep(poll_interval_seconds)
                if self._stop_requested.is_set():
                    self.request_stop()
                    session.join(timeout=5.0)
                    break
                session.join()
                if max_sessions is not None and sessions_started >= max_sessions:
                    break
                delay = self.RECONNECT_DELAYS_SECONDS[backoff_index]
                backoff_index = 0 if self._healthy_session else min(backoff_index + 1, len(self.RECONNECT_DELAYS_SECONDS) - 1)
                self._event("RECONNECTING")
                # Permit Ctrl+C/request_stop to avoid waiting through a backoff.
                if wait_for_stop(delay):
                    break
        finally:
            self.request_stop()
            self._event("STOPPED")

    def _on_data(self, _, message):
        received_at = datetime.now(IST)
        self.last_callback_received_at = received_at
        try:
            exchange_type = message.get("exchange_type"); identity = next((key for key, value in MARKETS.items() if value["exchange_type"] == exchange_type and key[1] == str(message.get("token"))), None)
            if identity is None: raise Task9LiveTickError("unsupported websocket tick")
            timestamp = message.get("exchange_timestamp") or message.get("last_traded_timestamp")
            if isinstance(timestamp, (int, float)): timestamp = datetime.fromtimestamp(timestamp / 1000, IST)
            if not isinstance(timestamp, datetime): raise Task9LiveTickError("provider_timestamp")
            price = message.get("last_traded_price")
            if isinstance(price, int): price = price / 100
            tick = normalize_task9_websocket_tick(exchange=identity[0], symbol_token=identity[1], provider_timestamp=timestamp, received_at=received_at, ltp=price)
            self.journal.append(tick)
            self.last_valid_tick_received_at = received_at
            self.latest_provider_timestamp = tick.provider_timestamp
            self._healthy_session = True
            if self.health(now=received_at)["state"] == "LAGGING_BACKLOG" and not self._lagging_backlog_reported:
                self._event("LAGGING_BACKLOG")
                self._lagging_backlog_reported = True
        except Task9LiveTickError: self._event("REJECTED_TICK")
