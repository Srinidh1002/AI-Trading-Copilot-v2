from datetime import datetime, timedelta

from services.historical_data_cache import HistoricalDataCache
from services.market.live_multi_timeframe_data import (
    LiveMultiTimeframeData,
    required_closed_candle_at,
)
from services.market.task9_historical_websocket_composition import (
    Task9HistoricalWebsocketComposition,
)
from services.market.task9_live_tick_stream import Task9LiveTickJournal, normalize_task9_websocket_tick


IST = __import__("zoneinfo").ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 8, 11, 13, 15, tzinfo=IST)


def _daily_response(required, *, count=55):
    return {
        "status": True,
        "data": [
            [
                (required - timedelta(days=count - index - 1)).isoformat(),
                24000.0 + index,
                24002.0 + index,
                23998.0 + index,
                24001.0 + index,
                1000,
            ]
            for index in range(count)
        ],
    }


class _DailyHistoricalClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get_historical_data(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def _session_resolver(
    *,
    market,
    evaluated_at,
    market_date,
):
    from datetime import time

    from services.contracts.task9_market_session_policy_v1 import (
        Task9MarketSegment,
        Task9SessionPhase,
    )
    from services.contracts.task9_market_session_state_v1 import (
        Task9SegmentSessionStateV1,
    )

    return Task9SegmentSessionStateV1(
        segment=(
            Task9MarketSegment.NFO_OPTIONS
            if market == "NIFTY"
            else Task9MarketSegment.BFO_OPTIONS
        ),
        market_date=market_date,
        evaluated_at=evaluated_at,
        timezone="Asia/Kolkata",
        phase=Task9SessionPhase.OPEN,
        market_open=True,
        new_entries_allowed=True,
        position_monitoring_allowed=True,
        close_drain_required=False,
        session_open_time=time(9, 15),
        new_entry_cutoff=time(15, 30),
        position_monitoring_until=time(15, 40),
        session_close_time=time(15, 40),
        calendar_status="TRADING_DAY",
        policy_id="task925-session-policy",
        policy_version="1",
    )


def test_historical_only_and_daily_never_uses_websocket(tmp_path):
    adapter = Task9HistoricalWebsocketComposition(live_stream_root=tmp_path)
    row = ("2026-08-10T00:00:00+05:30", 1, 2, 1, 2, 1)
    result = adapter.compose(market="NIFTY", trading_date=NOW.date(), timeframe="1d", as_of=NOW, historical_rows=(row,))
    assert result.ready is True and result.source_composition == ("HISTORICAL_CACHE",)


def test_successful_daily_warmup_feeds_real_cache_only_task9_composition(tmp_path):
    required = required_closed_candle_at("1d", NOW, exchange="NSE")
    client = _DailyHistoricalClient(_daily_response(required))
    cache = HistoricalDataCache(tmp_path / "historical.json", time_function=lambda: 1.0)
    service = LiveMultiTimeframeData(client=client, cache=cache)

    warmup = service.ensure_daily_cache_coverage("NSE", "99926000", end_time=NOW)
    cached = cache.get_incremental_candidate("NSE", "99926000", "1d")
    result = Task9HistoricalWebsocketComposition(live_stream_root=tmp_path).compose(
        market="NIFTY",
        trading_date=NOW.date(),
        timeframe="1d",
        as_of=NOW,
        historical_rows=tuple(cached["response"]["data"]),
    )

    assert warmup["refresh_outcome"] == "REFRESHED"
    assert len(client.calls) == 1
    assert result.ready is True
    assert result.source_composition == ("HISTORICAL_CACHE",)


def test_missing_intraday_evidence_fails_closed_without_provider_work(tmp_path):
    result = Task9HistoricalWebsocketComposition(live_stream_root=tmp_path).compose(market="SENSEX", trading_date=NOW.date(), timeframe="5m", as_of=NOW)
    assert result.ready is False and result.failure_reason == "TIMEFRAME_UNAVAILABLE" and result.available_bar_count == 0


def _late_nifty_tick(offset):
    timestamp = datetime(2026, 8, 11, 9, 15, tzinfo=IST) + timedelta(minutes=offset)
    return normalize_task9_websocket_tick(exchange="NSE", symbol_token="99926000", provider_timestamp=timestamp, received_at=timestamp, ltp=25000)


def test_composition_rejects_partial_closed_websocket_bucket(tmp_path):
    adapter = Task9HistoricalWebsocketComposition(live_stream_root=tmp_path)
    partial_start = "2026-08-11T09:25:00+05:30"
    # Defend the composition seam itself: a populated aggregator result is not
    # authoritative when its paired coverage result withholds certification.
    adapter.aggregator.candles = lambda **_: ({"start_at": partial_start},)
    adapter.aggregator.coverage = lambda **_: {"complete_closed_starts": ()}

    result = adapter.compose(
        market="NIFTY", trading_date=NOW.date(), timeframe="5m",
        as_of=datetime(2026, 8, 11, 9, 40, tzinfo=IST),
    )

    assert result.ready is False and result.failure_reason == "TIMEFRAME_UNAVAILABLE"


def test_composition_allows_valid_historical_cache_when_websocket_bucket_is_partial(tmp_path):
    journal = Task9LiveTickJournal(
        tmp_path,
        session_state_resolver=_session_resolver,
    )
    journal.append(_late_nifty_tick(12))
    cached = ("2026-08-11T09:35:00+05:30", 1, 2, 1, 2, 1)

    result = Task9HistoricalWebsocketComposition(live_stream_root=tmp_path).compose(
        market="NIFTY", trading_date=NOW.date(), timeframe="5m",
        as_of=datetime(2026, 8, 11, 9, 40, tzinfo=IST), historical_rows=(cached,),
    )

    assert result.ready is True and result.source_composition == ("HISTORICAL_CACHE",)


def test_certified_websocket_can_satisfy_exact_5m_and_15m_identities(tmp_path):
    journal = Task9LiveTickJournal(
        tmp_path,
        session_state_resolver=_session_resolver,
    )
    for offset in range(0, 50, 5):
        journal.append(_late_nifty_tick(offset))
    adapter = Task9HistoricalWebsocketComposition(
        live_stream_root=tmp_path,
        session_state_resolver=_session_resolver,
    )
    as_of = datetime(2026, 8, 11, 10, 8, tzinfo=IST)

    five = adapter.compose(market="NIFTY", trading_date=as_of.date(), timeframe="5m", as_of=as_of)
    fifteen = adapter.compose(market="NIFTY", trading_date=as_of.date(), timeframe="15m", as_of=as_of)

    assert five.ready is True and five.source_composition == ("LIVE_WEBSOCKET",)
    assert fifteen.ready is True and fifteen.source_composition == ("LIVE_WEBSOCKET",)


def test_daily_composition_never_reads_websocket_evidence(tmp_path):
    adapter = Task9HistoricalWebsocketComposition(live_stream_root=tmp_path)
    adapter.aggregator.candles = lambda **_: (_ for _ in ()).throw(AssertionError("websocket"))
    adapter.aggregator.coverage = lambda **_: (_ for _ in ()).throw(AssertionError("websocket"))

    result = adapter.compose(
        market="NIFTY", trading_date=NOW.date(), timeframe="1d", as_of=NOW,
        historical_rows=(("2026-08-10T00:00:00+05:30", 1, 2, 1, 2, 1),),
    )

    assert result.ready is True and result.source_composition == ("HISTORICAL_CACHE",)


def test_stale_daily_cache_cannot_satisfy_exact_required_trading_date(tmp_path):
    result = Task9HistoricalWebsocketComposition(live_stream_root=tmp_path).compose(
        market="NIFTY", trading_date=NOW.date(), timeframe="1d", as_of=NOW,
        historical_rows=(("2026-08-08T00:00:00+05:30", 1, 2, 1, 2, 1),),
    )

    assert result.ready is False and result.failure_reason == "TIMEFRAME_UNAVAILABLE"
    assert result.missing_interval_identities == ("2026-08-10T00:00:00+05:30",)


def test_stale_5m_and_15m_cache_cannot_satisfy_todays_required_identity(tmp_path):
    adapter = Task9HistoricalWebsocketComposition(live_stream_root=tmp_path)
    as_of = datetime(2026, 8, 11, 10, 8, tzinfo=IST)
    stale = ("2026-08-10T10:00:00+05:30", 1, 2, 1, 2, 1)

    five = adapter.compose(market="NIFTY", trading_date=as_of.date(), timeframe="5m", as_of=as_of, historical_rows=(stale,))
    fifteen = adapter.compose(market="NIFTY", trading_date=as_of.date(), timeframe="15m", as_of=as_of, historical_rows=(stale,))

    assert five.ready is False and five.missing_interval_identities == ("2026-08-11T10:00:00+05:30",)
    assert fifteen.ready is False and fifteen.missing_interval_identities == ("2026-08-11T09:45:00+05:30",)


def test_hourly_composition_uses_same_session_15_minute_effective_identity(tmp_path):
    adapter = Task9HistoricalWebsocketComposition(live_stream_root=tmp_path)
    as_of = datetime(2026, 8, 11, 10, 17, tzinfo=IST)
    equivalent = ("2026-08-11T09:15:00+05:30", 1, 2, 1, 2, 1)
    stale = ("2026-08-10T09:15:00+05:30", 1, 2, 1, 2, 1)

    ready = adapter.compose(market="NIFTY", trading_date=as_of.date(), timeframe="1h", as_of=as_of, historical_rows=(equivalent,))
    unavailable = adapter.compose(market="NIFTY", trading_date=as_of.date(), timeframe="1h", as_of=as_of, historical_rows=(stale,))

    assert ready.ready is True and ready.earliest_required_timestamp == equivalent[0]
    assert unavailable.ready is False and unavailable.missing_interval_identities == (equivalent[0],)


def test_later_hourly_slot_requires_its_own_session_anchored_identity(tmp_path):
    as_of = datetime(2026, 8, 11, 11, 17, tzinfo=IST)
    result = Task9HistoricalWebsocketComposition(live_stream_root=tmp_path).compose(
        market="NIFTY", trading_date=as_of.date(), timeframe="1h", as_of=as_of,
        historical_rows=(("2026-08-11T09:15:00+05:30", 1, 2, 1, 2, 1),),
    )

    assert result.ready is False
    assert result.missing_interval_identities == ("2026-08-11T10:15:00+05:30",)
def test_hourly_effective_identity_waits_for_session_aligned_close():
    from services.market.task9_historical_websocket_composition import (
        _effective_required_candle_at,
    )
    from services.market.live_multi_timeframe_data import (
        required_closed_candle_at,
    )

    cases = (
        (
            datetime(2026, 8, 13, 13, 59, 59, tzinfo=IST),
            "2026-08-13T12:15:00+05:30",
        ),
        (
            datetime(2026, 8, 13, 14, 0, tzinfo=IST),
            "2026-08-13T12:15:00+05:30",
        ),
        (
            datetime(2026, 8, 13, 14, 7, tzinfo=IST),
            "2026-08-13T12:15:00+05:30",
        ),
        (
            datetime(2026, 8, 13, 14, 14, 59, tzinfo=IST),
            "2026-08-13T12:15:00+05:30",
        ),
        (
            datetime(2026, 8, 13, 14, 15, tzinfo=IST),
            "2026-08-13T13:15:00+05:30",
        ),
        (
            datetime(2026, 8, 13, 14, 15, 1, tzinfo=IST),
            "2026-08-13T13:15:00+05:30",
        ),
    )

    for as_of, expected in cases:
        shared = required_closed_candle_at(
            "1h",
            as_of,
            exchange="NSE",
        )

        effective = _effective_required_candle_at(
            timeframe="1h",
            required_closed_at=shared,
            as_of=as_of,
            exchange="NSE",
        )

        assert effective.isoformat() == expected


def test_hourly_effective_identity_preserves_existing_session_boundaries():
    from services.market.task9_historical_websocket_composition import (
        _effective_required_candle_at,
    )
    from services.market.live_multi_timeframe_data import (
        required_closed_candle_at,
    )

    cases = (
        (
            datetime(2026, 8, 11, 10, 17, tzinfo=IST),
            "2026-08-11T09:15:00+05:30",
        ),
        (
            datetime(2026, 8, 11, 11, 17, tzinfo=IST),
            "2026-08-11T10:15:00+05:30",
        ),
    )

    for as_of, expected in cases:
        shared = required_closed_candle_at(
            "1h",
            as_of,
            exchange="NSE",
        )

        effective = _effective_required_candle_at(
            timeframe="1h",
            required_closed_at=shared,
            as_of=as_of,
            exchange="NSE",
        )

        assert effective.isoformat() == expected
def test_precomposed_factory_requires_session_state_authority(
    tmp_path,
):
    import pytest

    from services.market.task9_historical_websocket_composition import (
        build_task9_precomposed_timeframe_provider,
    )

    with pytest.raises(
        TypeError,
        match="session_state_resolver",
    ):
        build_task9_precomposed_timeframe_provider(
            live_stream_root=tmp_path,
            session_state_resolver=None,
        )
