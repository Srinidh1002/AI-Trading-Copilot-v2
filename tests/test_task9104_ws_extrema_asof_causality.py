from __future__ import annotations

from datetime import timedelta

from services.certification.task9_abstention_later_observation_recovery import (
    _backfill_empty_abstention_window_from_live_ticks,
)
from services.market.task9_live_tick_stream import (
    Task9LiveTickJournal,
    Task9LiveTickV1,
)
from tests.test_task9104_abstention_ws_extrema_backfill import (
    _initialize,
    _runtime,
)


def _tick(
    prediction,
    *,
    provider_timestamp,
    received_at,
    price,
):
    if (
        prediction.underlying_symbol,
        prediction.exchange,
    ) == (
        "NIFTY",
        "NSE",
    ):
        symbol_token = "99926000"
    elif (
        prediction.underlying_symbol,
        prediction.exchange,
    ) == (
        "SENSEX",
        "BSE",
    ):
        symbol_token = "99919000"
    else:
        raise AssertionError(
            "unexpected Task9 market identity"
        )

    return Task9LiveTickV1(
        market=prediction.underlying_symbol,
        exchange=prediction.exchange,
        symbol_token=symbol_token,
        provider_timestamp=provider_timestamp,
        received_at=received_at,
        ltp=float(price),
    )


def test_ws_extrema_backfill_ignores_tick_received_after_evaluation_boundary(
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

    context = (
        runtime["context_store"]
        .recover(
            prediction.prediction_id
        )
    )

    assert context is not None

    evaluated_at = (
        context.validity_window_ends_at
    )

    window_span = (
        context.validity_window_ends_at
        - prediction.completed_at
    )

    assert window_span.total_seconds() > 0

    early_provider_timestamp = (
        prediction.completed_at
        + window_span / 3
    )

    late_provider_timestamp = (
        prediction.completed_at
        + (window_span * 2) / 3
    )

    assert (
        prediction.completed_at
        < early_provider_timestamp
        < late_provider_timestamp
        <= context.validity_window_ends_at
    )

    early_tick = _tick(
        prediction,
        provider_timestamp=(
            early_provider_timestamp
        ),
        received_at=(
            early_provider_timestamp
            + timedelta(
                milliseconds=50
            )
        ),
        price=25001.0,
    )

    late_received_tick = _tick(
        prediction,
        provider_timestamp=(
            late_provider_timestamp
        ),
        received_at=(
            evaluated_at
            + timedelta(seconds=1)
        ),
        price=99999.0,
    )

    assert (
        early_tick.received_at
        <= evaluated_at
    )

    assert (
        late_received_tick.provider_timestamp
        <= context.validity_window_ends_at
    )

    assert (
        late_received_tick.received_at
        > evaluated_at
    )

    def fake_load(
        self,
        trading_date,
    ):
        return (
            early_tick,
            late_received_tick,
        )

    monkeypatch.setattr(
        Task9LiveTickJournal,
        "load",
        fake_load,
    )

    window = (
        _backfill_empty_abstention_window_from_live_ticks(
            prediction=prediction,
            context=context,
            observation_store=(
                runtime[
                    "observation_store"
                ]
            ),
            live_stream_root=(
                tmp_path
                / "live_stream"
            ),
            evaluated_at=evaluated_at,
        )
    )

    assert window is not None

    assert (
        window.observation_count
        == 1
    )

    assert tuple(
        item.observed_at
        for item
        in window.observations
    ) == (
        early_tick.provider_timestamp,
    )

    assert (
        window.lowest_underlying_price
        == early_tick.ltp
    )

    assert (
        window.highest_underlying_price
        == early_tick.ltp
    )

    assert all(
        item.underlying_price
        != late_received_tick.ltp
        for item
        in window.observations
    )


def test_ws_extrema_backfill_accepts_tick_received_exactly_at_evaluation_boundary(
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

    context = (
        runtime["context_store"]
        .recover(
            prediction.prediction_id
        )
    )

    assert context is not None

    evaluated_at = (
        context.validity_window_ends_at
    )

    window_span = (
        context.validity_window_ends_at
        - prediction.completed_at
    )

    provider_timestamp = (
        prediction.completed_at
        + window_span / 2
    )

    boundary_tick = _tick(
        prediction,
        provider_timestamp=(
            provider_timestamp
        ),
        received_at=evaluated_at,
        price=25002.0,
    )

    def fake_load(
        self,
        trading_date,
    ):
        return (
            boundary_tick,
        )

    monkeypatch.setattr(
        Task9LiveTickJournal,
        "load",
        fake_load,
    )

    window = (
        _backfill_empty_abstention_window_from_live_ticks(
            prediction=prediction,
            context=context,
            observation_store=(
                runtime[
                    "observation_store"
                ]
            ),
            live_stream_root=(
                tmp_path
                / "live_stream"
            ),
            evaluated_at=evaluated_at,
        )
    )

    assert window is not None

    assert (
        window.observation_count
        == 1
    )

    assert (
        window.observations[0]
        .observed_at
        == provider_timestamp
    )

    assert (
        window.observations[0]
        .underlying_price
        == boundary_tick.ltp
    )
