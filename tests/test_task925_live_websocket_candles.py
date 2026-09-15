from datetime import datetime, timedelta
from dataclasses import replace
import json
import time
from zoneinfo import ZoneInfo

import pytest

from services.certification.task9_live_collector_session_resolver import (
    build_task9_live_collector_session_resolver,
)
from services.market.task9_live_tick_stream import (
    IST,
    Task9LiveCandleAggregator,
    Task9LiveTickError,
    Task9LiveTickJournal,
    Task9LiveTickStream,
    normalize_task9_websocket_tick,
)


NOW = datetime(2026, 8, 11, 9, 15, tzinfo=IST)


def _session_resolver():
    return build_task9_live_collector_session_resolver(
        nfo_new_entry_cutoff=NOW.replace(
            hour=15,
            minute=20,
            second=0,
            microsecond=0,
        ).time(),
        bfo_new_entry_cutoff=NOW.replace(
            hour=15,
            minute=20,
            second=0,
            microsecond=0,
        ).time(),
    )


def _journal(root):
    return Task9LiveTickJournal(
        root,
        session_state_resolver=_session_resolver(),
    )


def _tick(offset=0, *, market="NIFTY", price=25000):
    exchange, token = ("NSE", "99926000") if market == "NIFTY" else ("BSE", "99919000")
    return normalize_task9_websocket_tick(exchange=exchange, symbol_token=token, provider_timestamp=NOW + timedelta(minutes=offset), received_at=NOW + timedelta(minutes=offset), ltp=price)


def test_exact_shared_subscriptions_and_no_socket_until_started(tmp_path):
    stream = Task9LiveTickStream(journal=_journal(tmp_path), websocket_factory=lambda **_: None, credentials={})
    assert stream.websocket is None
    assert Task9LiveTickStream.subscriptions() == [
        {"exchangeType": 1, "tokens": ["99926000"]},
        {"exchangeType": 3, "tokens": ["99919000"]},
    ]


class _FakeSocket:
    def __init__(self, *, healthy=False, block=False):
        self.healthy, self.block = healthy, block
        self.subscriptions = []
        self.closed = False

    def subscribe(self, correlation_id, mode, subscriptions):
        self.subscriptions.append((correlation_id, mode, subscriptions))

    def connect(self):
        self.on_open(self)
        if self.block:
            self._stream._session_opened_at = NOW + timedelta(hours=1)
        if self.healthy:
            # A valid data session resets the Task9 supervisor's backoff.
            self._stream._healthy_session = True
        while self.block and not self.closed:
            time.sleep(0.001)

    def close_connection(self):
        self.closed = True


def test_stream_explicit_callbacks_subscribe_once_and_never_expose_credentials(tmp_path):
    socket = _FakeSocket()
    stream = Task9LiveTickStream(
        journal=_journal(tmp_path),
        websocket_factory=lambda **_: socket,
        credentials={"auth_token": "secret", "feed_token": "secret"},
    )
    socket._stream = stream
    stream.start()
    socket.on_error(socket, "transport error")
    socket.on_close(socket)

    assert socket.subscriptions == [("task9-live-candles", 1, Task9LiveTickStream.subscriptions())]
    assert list(stream.events)[-4:] == ["CONNECTING", "OPEN", "ERROR", "CLOSED"]
    assert all("secret" not in event for event in stream.events)


def test_supervisor_reconnects_sequentially_with_bounded_backoff_and_healthy_reset(tmp_path):
    sockets = []
    healthy_by_session = (False, True, False, False, False)
    def factory(**_):
        socket = _FakeSocket(healthy=healthy_by_session[len(sockets)])
        socket._stream = stream
        sockets.append(socket)
        return socket
    stream = Task9LiveTickStream(journal=_journal(tmp_path), websocket_factory=factory, credentials={})
    delays = []

    stream.run_forever(
        clock=lambda: NOW + timedelta(hours=1),
        sleep=lambda _: None,
        wait_for_stop=lambda delay: delays.append(delay) or False,
        poll_interval_seconds=0.001,
        max_sessions=4,
    )

    assert len(sockets) == 4
    assert delays == [2.0, 5.0, 2.0]
    assert all(len(socket.subscriptions) == 1 for socket in sockets)
    assert list(stream.events)[-1] == "STOPPED"


def test_stale_open_connection_reconnects_only_during_market_session_and_stop_closes_socket(tmp_path):
    socket = _FakeSocket(block=True)
    stream = Task9LiveTickStream(journal=_journal(tmp_path), websocket_factory=lambda **_: socket, credentials={})
    socket._stream = stream
    stream.run_forever(
        clock=lambda: NOW + timedelta(hours=1, seconds=31),
        sleep=lambda _: time.sleep(0.001), poll_interval_seconds=0.001,
        max_sessions=1,
    )
    assert socket.closed is True
    assert "STALE" in stream.events and list(stream.events)[-1] == "STOPPED"


def test_closed_session_does_not_start_or_stale_websocket(tmp_path):
    socket = _FakeSocket()
    factory_calls = []

    def factory(**_):
        factory_calls.append(True)
        socket._stream = stream
        return socket

    stream = Task9LiveTickStream(
        journal=_journal(tmp_path),
        websocket_factory=factory,
        credentials={},
    )

    closed_session = NOW.replace(
        hour=16,
        minute=0,
        second=0,
        microsecond=0,
    )

    stream.run_forever(
        clock=lambda: closed_session,
        sleep=lambda _: None,
        poll_interval_seconds=0.001,
        max_sessions=1,
    )

    # The session resolver closes the supervisor before _prepare_session().
    # No socket should be created merely so final cleanup can close it.
    assert factory_calls == []
    assert stream.websocket is None
    assert socket.closed is False
    assert stream.close_reason != "STALE"
    assert "STALE" not in stream.events


def test_closed_ist_5m_15m_and_1h_candles_are_truthful_and_restart_safe(tmp_path):
    journal = _journal(tmp_path)
    for offset in range(0, 60, 5):
        assert journal.append(_tick(offset, price=25000 + offset)) is True
    aggregator = Task9LiveCandleAggregator(_journal(tmp_path))
    assert aggregator.candles(market="NIFTY", trading_date=NOW.date(), timeframe="5m", as_of=NOW + timedelta(minutes=5))[0]["close"] == 25000
    assert len(aggregator.candles(market="NIFTY", trading_date=NOW.date(), timeframe="15m", as_of=NOW + timedelta(minutes=15))) == 1
    assert len(aggregator.candles(market="NIFTY", trading_date=NOW.date(), timeframe="1h", as_of=NOW + timedelta(minutes=60))) == 1
    assert journal.append(_tick(0, price=25000)) is False


def test_rejects_malformed_out_of_order_and_out_of_session_ticks(tmp_path):
    journal = _journal(tmp_path)
    with pytest.raises(Task9LiveTickError): normalize_task9_websocket_tick(exchange="NSE", symbol_token="99926000", provider_timestamp=NOW, received_at=NOW, ltp=0)
    journal.append(_tick(5))
    with pytest.raises(Task9LiveTickError): journal.append(_tick(0))
    with pytest.raises(Task9LiveTickError): journal.append(normalize_task9_websocket_tick(exchange="NSE", symbol_token="99926000", provider_timestamp=NOW.replace(hour=8), received_at=NOW, ltp=25000))


def test_late_start_coverage_reports_missing_morning_without_synthesis(tmp_path):
    journal = _journal(tmp_path)
    journal.append(_tick(130))
    coverage = Task9LiveCandleAggregator(journal).coverage(market="NIFTY", trading_date=NOW.date(), timeframe="5m", as_of=NOW + timedelta(minutes=135))
    assert coverage["earliest_observed_at"] == (NOW + timedelta(minutes=130)).isoformat()
    assert NOW.isoformat() in coverage["missing_closed_starts"]
    assert coverage["complete_closed_starts"] == ((NOW + timedelta(minutes=130)).isoformat(),)


def test_late_capture_does_not_certify_the_partially_observed_5m_bucket(tmp_path):
    journal = _journal(tmp_path)
    journal.append(_tick(12))  # 09:27, after the 09:25 bucket began.
    aggregator = Task9LiveCandleAggregator(journal)

    coverage = aggregator.coverage(market="NIFTY", trading_date=NOW.date(), timeframe="5m", as_of=NOW + timedelta(minutes=20))
    assert (NOW + timedelta(minutes=10)).isoformat() in coverage["missing_closed_starts"]
    assert aggregator.candles(market="NIFTY", trading_date=NOW.date(), timeframe="5m", as_of=NOW + timedelta(minutes=20)) == ()


def test_late_capture_cannot_certify_15m_or_1h_session_start_windows(tmp_path):
    journal = _journal(tmp_path)
    for offset in (12, *range(15, 60, 5)):
        journal.append(_tick(offset))
    aggregator = Task9LiveCandleAggregator(journal)

    assert (NOW.isoformat() in aggregator.coverage(market="NIFTY", trading_date=NOW.date(), timeframe="15m", as_of=NOW + timedelta(minutes=30))["missing_closed_starts"])
    assert NOW.isoformat() not in tuple(item["start_at"] for item in aggregator.candles(market="NIFTY", trading_date=NOW.date(), timeframe="15m", as_of=NOW + timedelta(minutes=30)))
    assert (NOW.isoformat() in aggregator.coverage(market="NIFTY", trading_date=NOW.date(), timeframe="1h", as_of=NOW + timedelta(minutes=60))["missing_closed_starts"])
    assert aggregator.candles(market="NIFTY", trading_date=NOW.date(), timeframe="1h", as_of=NOW + timedelta(minutes=60)) == ()


def test_complete_capture_certifies_5m_15m_and_1h_normally(tmp_path):
    journal = _journal(tmp_path)
    for offset in range(0, 60, 5):
        journal.append(_tick(offset))
    aggregator = Task9LiveCandleAggregator(journal)

    assert len(aggregator.candles(market="NIFTY", trading_date=NOW.date(), timeframe="5m", as_of=NOW + timedelta(minutes=60))) == 12
    assert len(aggregator.candles(market="NIFTY", trading_date=NOW.date(), timeframe="15m", as_of=NOW + timedelta(minutes=60))) == 4
    assert len(aggregator.candles(market="NIFTY", trading_date=NOW.date(), timeframe="1h", as_of=NOW + timedelta(minutes=60))) == 1


def test_missing_constituent_5m_bucket_fails_higher_timeframe_closed_window(tmp_path):
    journal = _journal(tmp_path)
    for offset in range(0, 60, 5):
        if offset != 10:
            journal.append(_tick(offset))
    aggregator = Task9LiveCandleAggregator(journal)

    assert NOW.isoformat() in aggregator.coverage(market="NIFTY", trading_date=NOW.date(), timeframe="15m", as_of=NOW + timedelta(minutes=60))["missing_closed_starts"]
    assert NOW.isoformat() in aggregator.coverage(market="NIFTY", trading_date=NOW.date(), timeframe="1h", as_of=NOW + timedelta(minutes=60))["missing_closed_starts"]


def test_legacy_json_and_new_jsonl_are_combined_without_mutating_legacy_evidence(tmp_path):
    journal = _journal(tmp_path)
    legacy_tick = _tick(0)
    legacy_path = tmp_path / f"ticks-{NOW.date().isoformat()}.json"
    legacy_payload = {"schema_version": 1, "trading_date": NOW.date().isoformat(), "ticks": [{"market": legacy_tick.market, "exchange": legacy_tick.exchange, "symbol_token": legacy_tick.symbol_token, "provider_timestamp": legacy_tick.provider_timestamp.isoformat(), "received_at": legacy_tick.received_at.isoformat(), "ltp": legacy_tick.ltp, "source": legacy_tick.source}]}
    legacy_path.write_text(json.dumps(legacy_payload), encoding="utf-8")
    before = legacy_path.read_bytes()

    assert journal.append(_tick(5)) is True
    assert legacy_path.read_bytes() == before
    assert len(journal.load(NOW.date())) == 2
    assert (tmp_path / f"ticks-{NOW.date().isoformat()}.jsonl").exists()


def test_jsonl_append_seeds_state_once_and_does_not_rewrite_prior_records(tmp_path):
    journal = _journal(tmp_path)
    calls = 0
    original_load = journal.load
    def counted_load(day):
        nonlocal calls
        calls += 1
        return original_load(day)
    journal.load = counted_load

    for second in range(1000):
        assert journal.append(replace(_tick(0, price=25000 + second), provider_timestamp=NOW + timedelta(seconds=second), received_at=NOW + timedelta(seconds=second))) is True

    path = tmp_path / f"ticks-{NOW.date().isoformat()}.jsonl"
    before = path.read_bytes()
    duplicate = replace(_tick(0, price=25000), provider_timestamp=NOW, received_at=NOW)
    assert journal.append(duplicate) is False
    assert path.read_bytes() == before
    assert calls == 1
    assert len(journal.load(NOW.date())) == 1000


def test_jsonl_restart_ignores_only_incomplete_trailing_line_and_seeds_order_state(tmp_path):
    journal = _journal(tmp_path)
    assert journal.append(_tick(0)) is True
    path = tmp_path / f"ticks-{NOW.date().isoformat()}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"incomplete"')

    restarted = _journal(tmp_path)
    assert restarted.load(NOW.date()) == (_tick(0),)
    assert restarted.append(_tick(5)) is True
    with pytest.raises(Task9LiveTickError):
        restarted.append(_tick(1))


def test_lagging_callback_backlog_is_diagnostic_while_provider_timestamp_remains_authority(tmp_path):
    stream = Task9LiveTickStream(journal=_journal(tmp_path), websocket_factory=lambda **_: None, credentials={})
    stream._session_open = True
    stream.last_callback_received_at = NOW + timedelta(minutes=60)
    stream.latest_provider_timestamp = NOW

    health = stream.health(now=NOW + timedelta(minutes=1))
    assert health["state"] == "LAGGING_BACKLOG"
    assert health["latest_provider_timestamp"] == NOW.isoformat()
    assert health["provider_timestamp_authority"] is True


def test_malformed_newline_terminated_middle_jsonl_line_fails_closed(tmp_path):
    journal = _journal(tmp_path)
    assert journal.append(_tick(0)) is True
    path = tmp_path / f"ticks-{NOW.date().isoformat()}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"malformed":true}\n')
        handle.write(json.dumps({"market":"NIFTY","exchange":"NSE","symbol_token":"99926000","provider_timestamp":(NOW + timedelta(minutes=5)).isoformat(),"received_at":(NOW + timedelta(minutes=5)).isoformat(),"ltp":25001,"source":"LIVE_WEBSOCKET"}) + "\n")
    with pytest.raises(Task9LiveTickError):
        _journal(tmp_path).load(NOW.date())


def test_malformed_newline_terminated_final_jsonl_line_fails_closed(tmp_path):
    journal = _journal(tmp_path)
    assert journal.append(_tick(0)) is True
    with (tmp_path / f"ticks-{NOW.date().isoformat()}.jsonl").open("a", encoding="utf-8") as handle:
        handle.write('{"malformed":true}\n')
    with pytest.raises(Task9LiveTickError): _journal(tmp_path).load(NOW.date())


def test_unterminated_final_partial_jsonl_fragment_is_ignored_but_prior_rows_remain_readable(tmp_path):
    journal = _journal(tmp_path)
    assert journal.append(_tick(0)) is True
    assert journal.append(_tick(5)) is True
    path = tmp_path / f"ticks-{NOW.date().isoformat()}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"partial"')
    recovered = _journal(tmp_path).load(NOW.date())
    assert recovered == (_tick(0), _tick(5))
