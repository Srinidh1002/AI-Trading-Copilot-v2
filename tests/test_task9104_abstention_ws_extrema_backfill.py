from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import services.certification.task9_abstention_later_observation_recovery as recovery

from tests.test_task916_production_child_evidence_authority import (
    _runtime,
)
from tests.test_task926_abstention_later_observation_recovery import (
    _initialize,
    _policy,
)


def _tick(prediction, *, minutes, price, market=None, exchange=None):
    observed_at = (
        prediction.completed_at
        + timedelta(minutes=minutes)
    )

    return SimpleNamespace(
        market=(
            prediction.underlying_symbol
            if market is None
            else market
        ),
        exchange=(
            prediction.exchange
            if exchange is None
            else exchange
        ),
        symbol_token=(
            "99926000"
            if prediction.underlying_symbol == "NIFTY"
            else "99919000"
        ),
        provider_timestamp=observed_at,
        received_at=(
            observed_at
            + timedelta(milliseconds=50)
        ),
        ltp=float(price),
    )


def test_expired_empty_abstention_backfills_real_ws_extrema_and_resolves(
    tmp_path,
    monkeypatch,
):
    runtime = _runtime(
        tmp_path,
        nifty_action="NO_TRADE",
        sensex_action="NO_TRADE",
    )

    prediction = runtime["predictions"][0]

    _initialize(
        runtime,
        prediction,
    )

    context = runtime["context_store"].recover(
        prediction.prediction_id
    )

    assert (
        runtime["observation_store"]
        .recover(prediction.prediction_id)
        .observation_count
        == 0
    )

    low = _tick(
        prediction,
        minutes=2,
        price=(
            prediction.start_underlying_price
            - 20.0
        ),
    )

    high = _tick(
        prediction,
        minutes=10,
        price=(
            prediction.start_underlying_price
            + 30.0
        ),
    )

    # These must never be consumed.
    wrong_market = _tick(
        prediction,
        minutes=5,
        price=(
            prediction.start_underlying_price
            + 500.0
        ),
        market="SENSEX"
        if prediction.underlying_symbol == "NIFTY"
        else "NIFTY",
        exchange="BSE"
        if prediction.exchange == "NSE"
        else "NSE",
    )

    outside_window = _tick(
        prediction,
        minutes=16,
        price=(
            prediction.start_underlying_price
            + 1000.0
        ),
    )

    class _Journal:
        def __init__(self, root):
            assert root == tmp_path / "live_stream"

        def load(self, trading_date):
            assert (
                trading_date
                == context.validity_window_ends_at.date()
            )

            return (
                wrong_market,
                low,
                high,
                outside_window,
            )

    monkeypatch.setattr(
        recovery,
        "Task9LiveTickJournal",
        _Journal,
    )

    finalized = (
        recovery.finalize_task9_expired_abstentions(
            prediction_ledger=runtime["ledger"],
            lifecycle_context_store=(
                runtime["context_store"]
            ),
            observation_store=(
                runtime["observation_store"]
            ),
            outcome_store=runtime["outcome_store"],
            outcome_policy=_policy(),
            evaluated_at=(
                context.validity_window_ends_at
            ),
            live_stream_root=(
                tmp_path / "live_stream"
            ),
        )
    )

    assert prediction.prediction_id in finalized

    window = (
        runtime["observation_store"]
        .recover(prediction.prediction_id)
    )

    assert window.observation_count == 2

    assert (
        window.lowest_underlying_price
        == low.ltp
    )

    assert (
        window.highest_underlying_price
        == high.ltp
    )

    assert tuple(
        item.observed_at
        for item in window.observations
    ) == (
        low.provider_timestamp,
        high.provider_timestamp,
    )

    assert all(
        item.event_type == "NONE"
        and item.data_available is True
        and item.option_premium is None
        for item in window.observations
    )

    outcome = runtime["outcome_store"].recover(
        prediction.prediction_id
    )

    assert outcome is not None
    assert outcome.evaluation_status == "RESOLVED"

    assert (
        "UNDERLYING_EXTREMA_UNAVAILABLE"
        not in outcome.blockers
    )


def test_empty_abstention_without_qualifying_ws_ticks_stays_fail_closed(
    tmp_path,
    monkeypatch,
):
    runtime = _runtime(
        tmp_path,
        nifty_action="NO_TRADE",
        sensex_action="NO_TRADE",
    )

    prediction = runtime["predictions"][0]

    _initialize(
        runtime,
        prediction,
    )

    context = runtime["context_store"].recover(
        prediction.prediction_id
    )

    class _Journal:
        def __init__(self, root):
            pass

        def load(self, trading_date):
            return ()

    monkeypatch.setattr(
        recovery,
        "Task9LiveTickJournal",
        _Journal,
    )

    finalized = (
        recovery.finalize_task9_expired_abstentions(
            prediction_ledger=runtime["ledger"],
            lifecycle_context_store=(
                runtime["context_store"]
            ),
            observation_store=(
                runtime["observation_store"]
            ),
            outcome_store=runtime["outcome_store"],
            outcome_policy=_policy(),
            evaluated_at=(
                context.validity_window_ends_at
            ),
            live_stream_root=(
                tmp_path / "live_stream"
            ),
        )
    )

    assert prediction.prediction_id in finalized

    window = (
        runtime["observation_store"]
        .recover(prediction.prediction_id)
    )

    assert window.observation_count == 0

    outcome = runtime["outcome_store"].recover(
        prediction.prediction_id
    )

    assert outcome is not None
    assert outcome.evaluation_status == "DATA_UNAVAILABLE"

    assert outcome.blockers == (
        "UNDERLYING_EXTREMA_UNAVAILABLE",
    )
