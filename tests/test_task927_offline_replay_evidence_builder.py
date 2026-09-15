from datetime import date, datetime, time, timedelta

import pytest

from services.certification.task9_market_session_evaluator import (
    evaluate_task9_market_session,
)
from services.contracts.task9_market_session_policy_v1 import (
    Task9MarketSegment,
    build_task9_market_session_policy,
)
from services.certification.task9_historical_certification_replay import (
    LIVE_ROOT,
    REPLAY_ROOT,
    Task9HistoricalReplayError,
    Task9HistoricalReplayReceiptStore,
)
from services.certification.task9_offline_replay_evidence_builder import (
    build_offline_replay_evidence,
)
from services.market.task9_live_tick_stream import (
    IST,
    Task9LiveTickJournal,
    normalize_task9_websocket_tick,
)


DAY = date(2026, 8, 11)


_TEST_SESSION_POLICY = build_task9_market_session_policy(
    policy_id="task927-offline-replay-test-policy",
    policy_version="1",
    calendar_authority_ref="task927-offline-replay-test-calendar",
    nfo_new_entry_cutoff=time(15, 30),
    bfo_new_entry_cutoff=time(15, 30),
)


def _session_state_resolver(
    *,
    market,
    evaluated_at,
    market_date,
):
    aggregate = evaluate_task9_market_session(
        policy=_TEST_SESSION_POLICY,
        evaluated_at=evaluated_at,
        market_date=market_date,
        calendar_state="TRADING_DAY",
    )

    expected_segment = {
        "NIFTY": Task9MarketSegment.NFO_OPTIONS,
        "SENSEX": Task9MarketSegment.BFO_OPTIONS,
    }[market]

    return next(
        state
        for state in aggregate.states
        if state.segment is expected_segment
    )


@pytest.mark.parametrize(
    "root",
    (
        LIVE_ROOT,
        LIVE_ROOT / ".." / "task9",
    ),
)
def test_replay_receipt_store_rejects_live_root_after_normalization(root):
    with pytest.raises(
        Task9HistoricalReplayError,
        match="HISTORICAL_REPLAY_LIVE_ROOT_FORBIDDEN",
    ):
        Task9HistoricalReplayReceiptStore(root)


def test_replay_receipt_store_allows_replay_and_isolated_roots(tmp_path):
    assert Task9HistoricalReplayReceiptStore(REPLAY_ROOT).root == REPLAY_ROOT
    assert (
        Task9HistoricalReplayReceiptStore(tmp_path / "isolated").root
        == tmp_path / "isolated"
    )


def _ticks(root):
    journal = Task9LiveTickJournal(
        root,
        session_state_resolver=_session_state_resolver,
    )
    start = datetime(2026, 8, 11, 9, 15, tzinfo=IST)

    for exchange, token, price in (
        ("NSE", "99926000", 25000),
        ("BSE", "99919000", 80000),
    ):
        for minute in range(0, 375, 5):
            stamp = start + timedelta(minutes=minute)

            journal.append(
                normalize_task9_websocket_tick(
                    exchange=exchange,
                    symbol_token=token,
                    provider_timestamp=stamp,
                    received_at=stamp,
                    ltp=price + minute,
                )
            )

    return journal


def _daily(exchange, token, timeframe):
    assert timeframe == "1d"

    return (
        (
            "2026-08-10T00:00:00+05:30",
            1,
            2,
            1,
            2,
            1,
        ),
    )


def test_builder_aggregates_both_markets_deterministically_from_local_journal(
    tmp_path,
    monkeypatch,
):
    _ticks(tmp_path / "live")

    monkeypatch.setattr(
        "services.broker.shared_client.get_certification_market_client",
        lambda: (_ for _ in ()).throw(
            AssertionError("network")
        ),
    )

    first = build_offline_replay_evidence(
        trading_date=DAY,
        live_source_root=tmp_path / "live",
        output_file=tmp_path / "one.json",
        cache_reader=_daily,
        session_state_resolver=_session_state_resolver,
    )

    second = build_offline_replay_evidence(
        trading_date=DAY,
        live_source_root=tmp_path / "live",
        output_file=tmp_path / "two.json",
        cache_reader=_daily,
        session_state_resolver=_session_state_resolver,
    )

    assert first == second
    assert set(first) == {"NIFTY", "SENSEX"}

    assert all(
        set(value) == {"5m", "15m", "1h", "1d"}
        for value in first.values()
    )


def test_builder_fails_closed_for_missing_daily_and_live_output_collision(
    tmp_path,
):
    _ticks(tmp_path / "live")

    with pytest.raises(
        Task9HistoricalReplayError,
        match="REQUIRED_TIMEFRAME_MISSING_NIFTY_1d",
    ):
        build_offline_replay_evidence(
            trading_date=DAY,
            live_source_root=tmp_path / "live",
            output_file=tmp_path / "out.json",
            session_state_resolver=_session_state_resolver,
        )

    with pytest.raises(
        Task9HistoricalReplayError,
        match="HISTORICAL_REPLAY_LIVE_ROOT_FORBIDDEN",
    ):
        build_offline_replay_evidence(
            trading_date=DAY,
            live_source_root=tmp_path / "live",
            output_file=LIVE_ROOT / "evidence.json",
            cache_reader=_daily,
            session_state_resolver=_session_state_resolver,
        )

def test_builder_requires_explicit_canonical_session_authority(tmp_path):
    with pytest.raises(
        Task9HistoricalReplayError,
        match="HISTORICAL_REPLAY_SESSION_AUTHORITY_REQUIRED",
    ):
        build_offline_replay_evidence(
            trading_date=DAY,
            live_source_root=tmp_path / "live",
            output_file=tmp_path / "missing-authority.json",
            cache_reader=_daily,
        )
