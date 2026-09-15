from datetime import date, datetime, time
import time as wall_time
from zoneinfo import ZoneInfo

import pytest

from services.contracts.task9_market_session_policy_v1 import (
    Task9MarketSegment,
    Task9SessionPhase,
)
from services.contracts.task9_market_session_state_v1 import (
    Task9SegmentSessionStateV1,
)
from services.market.task9_live_tick_stream import (
    Task9LiveCandleAggregator,
    Task9LiveTickJournal,
    Task9LiveTickStream,
    task9_tick_stream_session_active,
)


IST = ZoneInfo("Asia/Kolkata")
MARKET_DATE = date(2026, 8, 17)


def _state(
    *,
    market: str,
    evaluated_at: datetime,
    phase: Task9SessionPhase,
    market_date: date = MARKET_DATE,
) -> Task9SegmentSessionStateV1:
    segment = {
        "NIFTY": Task9MarketSegment.NFO_OPTIONS,
        "SENSEX": Task9MarketSegment.BFO_OPTIONS,
    }[market]

    phase_flags = {
        Task9SessionPhase.PRE_OPEN: (False, False, False),
        Task9SessionPhase.OPEN: (True, True, True),
        Task9SessionPhase.ENTRY_RESTRICTED: (True, False, True),
        Task9SessionPhase.CLOSED: (False, False, False),
        Task9SessionPhase.NON_TRADING_DAY: (False, False, False),
    }

    market_open, entries_allowed, monitoring_allowed = phase_flags[phase]

    return Task9SegmentSessionStateV1(
        segment=segment,
        market_date=market_date,
        evaluated_at=evaluated_at,
        timezone="Asia/Kolkata",
        phase=phase,
        market_open=market_open,
        new_entries_allowed=entries_allowed,
        position_monitoring_allowed=monitoring_allowed,
        close_drain_required=False,
        session_open_time=time(9, 15),
        new_entry_cutoff=time(15, 30),
        position_monitoring_until=time(15, 40),
        session_close_time=time(15, 40),
        calendar_status="TRADING_DAY",
        policy_id="task9-test-session-policy",
        policy_version="1",
    )


def _resolver(*, market, evaluated_at, market_date):
    local = evaluated_at.astimezone(IST)
    wall = local.timetz().replace(tzinfo=None)

    if wall < time(9, 15):
        phase = Task9SessionPhase.PRE_OPEN
    elif wall < time(15, 30):
        phase = Task9SessionPhase.OPEN
    elif wall < time(15, 40):
        phase = Task9SessionPhase.ENTRY_RESTRICTED
    else:
        phase = Task9SessionPhase.CLOSED

    return _state(
        market=market,
        evaluated_at=local,
        phase=phase,
        market_date=market_date,
    )


def _stream(tmp_path):
    journal = Task9LiveTickJournal(
        tmp_path,
        session_state_resolver=_resolver,
    )
    return Task9LiveTickStream(
        journal=journal,
        websocket_factory=lambda **_: None,
        credentials={},
    )


@pytest.mark.parametrize(
    ("hour", "minute", "second", "expected"),
    (
        (15, 30, 0, True),
        (15, 39, 59, True),
        (15, 40, 0, False),
    ),
)
def test_task9_tick_stream_fno_boundary_uses_canonical_state(
    tmp_path,
    hour,
    minute,
    second,
    expected,
):
    stream = _stream(tmp_path)

    value = datetime(
        2026,
        8,
        17,
        hour,
        minute,
        second,
        tzinfo=IST,
    )

    assert stream._market_session_open(value) is expected


@pytest.mark.parametrize("market", ("NIFTY", "SENSEX"))
def test_entry_restricted_remains_monitoring_active(market):
    evaluated_at = datetime(
        2026,
        8,
        17,
        15,
        30,
        tzinfo=IST,
    )
    state = _resolver(
        market=market,
        evaluated_at=evaluated_at,
        market_date=MARKET_DATE,
    )

    assert state.phase is Task9SessionPhase.ENTRY_RESTRICTED
    assert state.new_entries_allowed is False
    assert state.position_monitoring_allowed is True

    assert task9_tick_stream_session_active(
        market=market,
        state=state,
        market_date=MARKET_DATE,
    )


@pytest.mark.parametrize(
    ("phase", "expected"),
    (
        (Task9SessionPhase.PRE_OPEN, False),
        (Task9SessionPhase.OPEN, True),
        (Task9SessionPhase.ENTRY_RESTRICTED, True),
        (Task9SessionPhase.CLOSED, False),
        (Task9SessionPhase.NON_TRADING_DAY, False),
    ),
)
def test_canonical_phase_controls_monitoring(phase, expected):
    evaluated_at = datetime(
        2026,
        8,
        17,
        12,
        0,
        tzinfo=IST,
    )
    state = _state(
        market="NIFTY",
        evaluated_at=evaluated_at,
        phase=phase,
    )

    assert (
        task9_tick_stream_session_active(
            market="NIFTY",
            state=state,
            market_date=MARKET_DATE,
        )
        is expected
    )


def test_missing_resolver_fails_closed(tmp_path):
    journal = Task9LiveTickJournal(tmp_path)

    stream = Task9LiveTickStream(
        journal=journal,
        websocket_factory=lambda **_: None,
        credentials={},
    )

    assert not stream._market_session_open(
        datetime(
            2026,
            8,
            17,
            12,
            0,
            tzinfo=IST,
        )
    )


def test_none_state_fails_closed():
    assert not task9_tick_stream_session_active(
        market="NIFTY",
        state=None,
        market_date=MARKET_DATE,
    )


def test_segment_mismatch_fails_closed():
    evaluated_at = datetime(
        2026,
        8,
        17,
        12,
        0,
        tzinfo=IST,
    )

    state = _state(
        market="SENSEX",
        evaluated_at=evaluated_at,
        phase=Task9SessionPhase.OPEN,
    )

    assert not task9_tick_stream_session_active(
        market="NIFTY",
        state=state,
        market_date=MARKET_DATE,
    )


def test_market_date_mismatch_fails_closed():
    evaluated_at = datetime(
        2026,
        8,
        17,
        12,
        0,
        tzinfo=IST,
    )

    state = _state(
        market="NIFTY",
        evaluated_at=evaluated_at,
        phase=Task9SessionPhase.OPEN,
    )

    assert not task9_tick_stream_session_active(
        market="NIFTY",
        state=state,
        market_date=date(2026, 8, 18),
    )


def test_candle_bucket_uses_canonical_session_boundary(tmp_path):
    journal = Task9LiveTickJournal(
        tmp_path,
        session_state_resolver=_resolver,
    )
    aggregator = Task9LiveCandleAggregator(journal)

    bucket_1530 = aggregator._bucket(
        market="NIFTY",
        timestamp=datetime(
            2026,
            8,
            17,
            15,
            30,
            tzinfo=IST,
        ),
        minutes=5,
    )

    bucket_1539 = aggregator._bucket(
        market="NIFTY",
        timestamp=datetime(
            2026,
            8,
            17,
            15,
            39,
            59,
            tzinfo=IST,
        ),
        minutes=5,
    )

    bucket_1540 = aggregator._bucket(
        market="NIFTY",
        timestamp=datetime(
            2026,
            8,
            17,
            15,
            40,
            tzinfo=IST,
        ),
        minutes=5,
    )

    assert bucket_1530 == datetime(
        2026,
        8,
        17,
        15,
        30,
        tzinfo=IST,
    )

    assert bucket_1539 == datetime(
        2026,
        8,
        17,
        15,
        35,
        tzinfo=IST,
    )

    assert bucket_1540 is None


def test_candle_missing_authority_fails_closed(tmp_path):
    journal = Task9LiveTickJournal(tmp_path)
    aggregator = Task9LiveCandleAggregator(journal)

    assert (
        aggregator._bucket(
            market="NIFTY",
            timestamp=datetime(
                2026,
                8,
                17,
                12,
                0,
                tzinfo=IST,
            ),
            minutes=5,
        )
        is None
    )


def test_health_session_gate_uses_canonical_resolver(tmp_path):
    stream = _stream(tmp_path)

    assert stream._market_session_open(
        datetime(
            2026,
            8,
            17,
            15,
            39,
            59,
            tzinfo=IST,
        )
    )

    assert not stream._market_session_open(
        datetime(
            2026,
            8,
            17,
            15,
            40,
            tzinfo=IST,
        )
    )


# =====================================================================
# Task 9.104 Gate 7X — collector canonical auto-shutdown
# =====================================================================


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    (
        (8, 0, False),
        (12, 0, False),
        (15, 30, False),
        (15, 39, False),
        (15, 40, True),
    ),
)
def test_collector_terminal_gate_does_not_confuse_entry_cutoff_with_close(
    tmp_path,
    hour,
    minute,
    expected,
):
    stream = _stream(tmp_path)

    evaluated_at = datetime(
        2026,
        8,
        17,
        hour,
        minute,
        tzinfo=IST,
    )

    assert (
        stream._all_market_sessions_terminal(
            evaluated_at
        )
        is expected
    )


def test_one_closed_market_does_not_stop_other_active_market(
    tmp_path,
):
    evaluated_at = datetime(
        2026,
        8,
        17,
        15,
        35,
        tzinfo=IST,
    )

    def mixed_resolver(
        *,
        market,
        evaluated_at,
        market_date,
    ):
        phase = (
            Task9SessionPhase.CLOSED
            if market == "NIFTY"
            else Task9SessionPhase.ENTRY_RESTRICTED
        )

        return _state(
            market=market,
            evaluated_at=evaluated_at,
            phase=phase,
            market_date=market_date,
        )

    stream = Task9LiveTickStream(
        journal=Task9LiveTickJournal(
            tmp_path,
            session_state_resolver=mixed_resolver,
        ),
        websocket_factory=lambda **_: None,
        credentials={},
    )

    assert not stream._all_market_sessions_terminal(
        evaluated_at
    )


def test_non_trading_day_is_terminal_for_both_markets(
    tmp_path,
):
    evaluated_at = datetime(
        2026,
        8,
        17,
        10,
        0,
        tzinfo=IST,
    )

    def non_trading_resolver(
        *,
        market,
        evaluated_at,
        market_date,
    ):
        return _state(
            market=market,
            evaluated_at=evaluated_at,
            phase=Task9SessionPhase.NON_TRADING_DAY,
            market_date=market_date,
        )

    stream = Task9LiveTickStream(
        journal=Task9LiveTickJournal(
            tmp_path,
            session_state_resolver=non_trading_resolver,
        ),
        websocket_factory=lambda **_: None,
        credentials={},
    )

    assert stream._all_market_sessions_terminal(
        evaluated_at
    )


class _Gate7XBlockingSocket:
    def __init__(self):
        self.closed = False
        self.subscriptions = []

    def subscribe(
        self,
        correlation_id,
        mode,
        subscriptions,
    ):
        self.subscriptions.append(
            (
                correlation_id,
                mode,
                subscriptions,
            )
        )

    def connect(self):
        self.on_open(self)

        while not self.closed:
            wall_time.sleep(0.001)

    def close_connection(self):
        self.closed = True


def test_supervisor_auto_stops_at_canonical_session_close(
    tmp_path,
):
    socket = _Gate7XBlockingSocket()
    sockets = []

    def factory(**_):
        sockets.append(socket)
        return socket

    stream = Task9LiveTickStream(
        journal=Task9LiveTickJournal(
            tmp_path,
            session_state_resolver=_resolver,
        ),
        websocket_factory=factory,
        credentials={},
    )

    before_close = datetime(
        2026,
        8,
        17,
        15,
        39,
        59,
        tzinfo=IST,
    )

    at_close = datetime(
        2026,
        8,
        17,
        15,
        40,
        0,
        tzinfo=IST,
    )

    values = iter(
        (
            before_close,
            at_close,
        )
    )

    def clock():
        return next(
            values,
            at_close,
        )

    stream.run_forever(
        clock=clock,
        sleep=lambda _: wall_time.sleep(
            0.001
        ),
        poll_interval_seconds=0.001,
    )

    assert len(sockets) == 1
    assert socket.closed is True

    assert (
        stream.close_reason
        == "SESSION_CLOSED"
    )

    assert (
        stream.session_close_state
        == "SESSION_CLOSED"
    )

    assert stream.reconnect_count == 0

    assert (
        list(stream.events)[-1]
        == "STOPPED"
    )


def test_supervisor_started_after_close_does_not_open_socket(
    tmp_path,
):
    sockets = []

    def factory(**_):
        sockets.append(
            _Gate7XBlockingSocket()
        )
        return sockets[-1]

    stream = Task9LiveTickStream(
        journal=Task9LiveTickJournal(
            tmp_path,
            session_state_resolver=_resolver,
        ),
        websocket_factory=factory,
        credentials={},
    )

    closed = datetime(
        2026,
        8,
        17,
        15,
        40,
        tzinfo=IST,
    )

    stream.run_forever(
        clock=lambda: closed,
        sleep=lambda _: None,
        poll_interval_seconds=0.001,
    )

    assert sockets == []

    assert (
        stream.close_reason
        == "SESSION_CLOSED"
    )

    assert (
        stream.session_close_state
        == "SESSION_CLOSED"
    )

    assert (
        list(stream.events)[-1]
        == "STOPPED"
    )


def test_explicit_request_stop_still_closes_current_socket(
    tmp_path,
):
    socket = _Gate7XBlockingSocket()

    stream = _stream(tmp_path)

    stream.websocket = socket

    stream.request_stop()

    assert (
        stream._stop_requested.is_set()
    )

    assert socket.closed is True

