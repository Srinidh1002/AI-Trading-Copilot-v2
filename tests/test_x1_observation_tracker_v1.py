from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from services.x1.observation_tracker_v1 import (
    InstrumentSilenceStateV1,
    ObservationQualityV1,
    ObservationTrackerV1,
    SessionStateV1,
)

BASE = datetime(2026, 9, 17, 10, 0, tzinfo=UTC)


def make_tracker(*, now=BASE, session_resolver=None):
    return ObservationTrackerV1(
        clock=lambda: now,
        session_state_resolver=session_resolver,
    )


def rec(
    *,
    symbol="NSE:NIFTY50-INDEX",
    ltp=100.0,
    ts=None,
    timestamp_source="PROVIDER",
    received_at=None,
    canonical_id="NIFTY:UNDERLYING",
):
    return {
        "provider": "FYERS",
        "provider_symbol": symbol,
        "ltp": ltp,
        "ts": ts or BASE,
        "timestamp_source": timestamp_source,
        "received_at": received_at or BASE,
        "canonical_instrument_id": canonical_id,
    }


def test_invalid_tracker_constructor_arguments():
    with pytest.raises(ValueError):
        ObservationTrackerV1(
            clock=lambda: BASE, stale_after_seconds=-1
        )
    with pytest.raises(ValueError):
        ObservationTrackerV1(clock=lambda: BASE, max_instruments=0)


def test_first_observation_is_valid():
    tracker = make_tracker()
    classification = tracker.classify(
        rec(), connection_generation=1, current_generation=1
    )
    assert classification.quality is ObservationQualityV1.VALID
    assert classification.is_valid


def test_exact_duplicate_is_classified_as_suspected_duplicate():
    tracker = make_tracker()
    tracker.classify(
        rec(), connection_generation=1, current_generation=1
    )
    second = tracker.classify(
        rec(), connection_generation=1, current_generation=1
    )
    assert (
        second.quality is ObservationQualityV1.SUSPECTED_DUPLICATE
    )
    assert not second.is_valid


def test_provider_repeat_ignores_receipt_time_change():
    tracker = make_tracker()
    tracker.classify(
        rec(), connection_generation=1, current_generation=1
    )
    later_receipt = BASE + timedelta(seconds=1)
    second = tracker.classify(
        rec(received_at=later_receipt),
        connection_generation=1,
        current_generation=1,
    )
    assert (
        second.quality is ObservationQualityV1.SUSPECTED_DUPLICATE
    )


def test_same_price_with_distinct_provider_timestamps_is_valid():
    tracker = make_tracker()
    t1 = BASE
    t2 = BASE + timedelta(seconds=1)
    a = tracker.classify(
        rec(ts=t1, ltp=100.0),
        connection_generation=1,
        current_generation=1,
    )
    b = tracker.classify(
        rec(ts=t2, ltp=100.0),
        connection_generation=1,
        current_generation=1,
    )
    assert a.quality is ObservationQualityV1.VALID
    assert b.quality is ObservationQualityV1.VALID


def test_out_of_order_provider_timestamp_is_refused():
    tracker = make_tracker()
    tracker.classify(
        rec(ts=BASE + timedelta(seconds=2)),
        connection_generation=1,
        current_generation=1,
    )
    ooo = tracker.classify(
        rec(ts=BASE + timedelta(seconds=1)),
        connection_generation=1,
        current_generation=1,
    )
    assert ooo.quality is ObservationQualityV1.OUT_OF_ORDER


def test_stale_generation_is_refused():
    tracker = make_tracker()
    stale = tracker.classify(
        rec(), connection_generation=1, current_generation=2
    )
    assert stale.quality is ObservationQualityV1.STALE_GENERATION


def test_future_dated_observation_is_refused():
    tracker = make_tracker()
    future_ts = BASE + timedelta(seconds=60)
    classification = tracker.classify(
        rec(ts=future_ts),
        connection_generation=1,
        current_generation=1,
    )
    assert (
        classification.quality is ObservationQualityV1.FUTURE_DATED
    )


def test_stale_dated_provider_timestamp_is_refused():
    tracker = ObservationTrackerV1(
        clock=lambda: BASE + timedelta(minutes=5),
        stale_after_seconds=30.0,
    )
    classification = tracker.classify(
        rec(ts=BASE),
        connection_generation=1,
        current_generation=1,
    )
    assert (
        classification.quality is ObservationQualityV1.STALE_DATED
    )


def test_missing_canonical_id_is_malformed():
    tracker = make_tracker()
    classification = tracker.classify(
        rec(canonical_id=""),
        connection_generation=1,
        current_generation=1,
    )
    assert classification.quality is ObservationQualityV1.MALFORMED
    assert (
        classification.reason_code
        == "missing_canonical_instrument_id"
    )


def test_invalid_price_is_malformed():
    tracker = make_tracker()
    bad = rec()
    bad["ltp"] = 0
    classification = tracker.classify(
        bad, connection_generation=1, current_generation=1
    )
    assert classification.quality is ObservationQualityV1.MALFORMED


def test_silence_before_any_tick_is_no_tick_yet():
    tracker = make_tracker()
    report = tracker.silence_report(
        "NIFTY:UNDERLYING", market_symbol="NIFTY"
    )
    assert report.state is InstrumentSilenceStateV1.NO_TICK_YET


def test_silence_after_valid_tick_is_active():
    tracker = make_tracker()
    tracker.classify(
        rec(), connection_generation=1, current_generation=1
    )
    report = tracker.silence_report(
        "NIFTY:UNDERLYING", market_symbol="NIFTY"
    )
    assert report.state is InstrumentSilenceStateV1.ACTIVE


def test_silence_after_stale_window_without_session_is_suspected():
    now = {"t": BASE}
    tracker = ObservationTrackerV1(
        clock=lambda: now["t"],
        stale_after_seconds=30.0,
    )
    tracker.classify(
        rec(), connection_generation=1, current_generation=1
    )
    now["t"] = BASE + timedelta(seconds=120)
    report = tracker.silence_report(
        "NIFTY:UNDERLYING", market_symbol="NIFTY"
    )
    assert (
        report.state is InstrumentSilenceStateV1.SUSPECTED_SILENCE
    )
    assert report.expected_active is True


def test_silence_during_inactive_market_is_expected():
    def resolver(*, market_symbol, evaluated_at, market_date):
        return SessionStateV1(
            market_symbol=market_symbol,
            market_date=market_date,
            is_active=False,
        )

    now = {"t": BASE}
    tracker = ObservationTrackerV1(
        clock=lambda: now["t"],
        stale_after_seconds=30.0,
        session_state_resolver=resolver,
    )
    tracker.classify(
        rec(), connection_generation=1, current_generation=1
    )
    now["t"] = BASE + timedelta(seconds=120)
    report = tracker.silence_report(
        "NIFTY:UNDERLYING", market_symbol="NIFTY"
    )
    assert (
        report.state is InstrumentSilenceStateV1.EXPECTED_INACTIVITY
    )


def test_silence_during_active_market_is_suspected():
    def resolver(*, market_symbol, evaluated_at, market_date):
        return SessionStateV1(
            market_symbol=market_symbol,
            market_date=market_date,
            is_active=True,
        )

    now = {"t": BASE}
    tracker = ObservationTrackerV1(
        clock=lambda: now["t"],
        stale_after_seconds=30.0,
        session_state_resolver=resolver,
    )
    tracker.classify(
        rec(), connection_generation=1, current_generation=1
    )
    now["t"] = BASE + timedelta(seconds=120)
    report = tracker.silence_report(
        "NIFTY:UNDERLYING", market_symbol="NIFTY"
    )
    assert (
        report.state is InstrumentSilenceStateV1.SUSPECTED_SILENCE
    )
    assert report.expected_active is True


def test_snapshot_reports_per_instrument_counters():
    tracker = make_tracker()
    tracker.classify(
        rec(), connection_generation=1, current_generation=1
    )
    tracker.classify(
        rec(), connection_generation=1, current_generation=1
    )
    snap = tracker.snapshot()
    assert snap["instrument_count"] == 1
    counts = snap["instruments"]["NIFTY:UNDERLYING"]
    assert counts["accepted_count"] == 1
    assert counts["duplicate_count"] == 1


def test_capacity_is_bounded():
    tracker = ObservationTrackerV1(
        clock=lambda: BASE, max_instruments=2
    )
    tracker.classify(
        rec(canonical_id="A"),
        connection_generation=1,
        current_generation=1,
    )
    tracker.classify(
        rec(canonical_id="B"),
        connection_generation=1,
        current_generation=1,
    )
    third = tracker.classify(
        rec(canonical_id="C"),
        connection_generation=1,
        current_generation=1,
    )
    assert third.quality is ObservationQualityV1.MALFORMED
    assert third.reason_code == "tracker_capacity_exceeded"
