from dataclasses import FrozenInstanceError, replace
from datetime import timedelta

import pytest

from services.contracts.prediction_observation_v1 import (
    PredictionObservationV1,
)
from services.prediction_outcomes.prediction_observation_window_tracker import (
    build_prediction_observation_window,
)
from test_r51_prediction_record_v1 import record


def observation(
    *,
    prediction=None,
    sequence_number=1,
    seconds=30,
    underlying_price=25010.0,
    option_premium=100.0,
    event_type="NONE",
    data_available=True,
    within_entry_window=True,
):
    prediction = prediction or record()
    return PredictionObservationV1(
        observation_id=f"observation-{sequence_number}",
        prediction_id=prediction.prediction_id,
        parent_cycle_id=prediction.parent_cycle_id,
        underlying_symbol=prediction.underlying_symbol,
        exchange=prediction.exchange,
        sequence_number=sequence_number,
        observed_at=(
            prediction.completed_at
            + timedelta(seconds=seconds)
        ),
        underlying_price=underlying_price,
        option_premium=option_premium,
        event_type=event_type,
        within_entry_window=within_entry_window,
        data_available=data_available,
        source_observation_id=(
            f"source-{sequence_number}"
            if data_available
            else None
        ),
    )


def build(prediction=None, observations=None):
    prediction = prediction or record()
    observations = (
        observations
        if observations is not None
        else (
            observation(
                prediction=prediction,
                sequence_number=1,
                seconds=30,
                underlying_price=25010.0,
                option_premium=100.0,
            ),
            observation(
                prediction=prediction,
                sequence_number=2,
                seconds=60,
                underlying_price=25020.0,
                option_premium=105.0,
                event_type="ENTRY",
            ),
            observation(
                prediction=prediction,
                sequence_number=3,
                seconds=90,
                underlying_price=25050.0,
                option_premium=125.0,
                event_type="T1",
            ),
        )
    )
    return build_prediction_observation_window(
        prediction=prediction,
        observations=observations,
        entry_window_ends_at=(
            prediction.completed_at
            + timedelta(minutes=5)
        ),
        validity_window_ends_at=(
            prediction.completed_at
            + timedelta(minutes=15)
        ),
    )


def test_window_is_immutable_deterministic_and_ordered():
    value = build()
    second = build(
        observations=tuple(
            reversed(build().observations)
        )
    )

    assert value == second
    assert value.to_json() == second.to_json()
    assert len(value.semantic_hash) == 64
    assert tuple(
        item.sequence_number
        for item in value.observations
    ) == (1, 2, 3)

    with pytest.raises(FrozenInstanceError):
        value.observation_count = 0


def test_tracks_entry_extrema_and_first_event():
    value = build()

    assert value.entry_occurred is True
    assert value.entry_premium == 105.0
    assert value.highest_option_premium == 125.0
    assert value.lowest_option_premium == 100.0
    assert value.highest_underlying_price == 25050.0
    assert value.lowest_underlying_price == 25010.0
    assert value.first_event_type == "ENTRY"
    assert value.terminal_event_type is None


def test_tracks_data_gap_and_session_close():
    prediction = record()
    gap = observation(
        prediction=prediction,
        sequence_number=1,
        seconds=30,
        underlying_price=None,
        option_premium=None,
        event_type="DATA_GAP",
        data_available=False,
        within_entry_window=False,
    )
    close = observation(
        prediction=prediction,
        sequence_number=2,
        seconds=600,
        underlying_price=25000.0,
        option_premium=None,
        event_type="SESSION_CLOSE",
        within_entry_window=False,
    )

    value = build(
        prediction=prediction,
        observations=(gap, close),
    )

    assert value.data_gap_count == 1
    assert value.first_data_gap_at == gap.observed_at
    assert value.session_closed is True
    assert value.session_closed_at == close.observed_at
    assert value.terminal_event_type == "SESSION_CLOSE"


def test_wait_prediction_needs_no_option_premium():
    prediction = record(
        predicted_direction="NEUTRAL",
        predicted_action="WAIT",
        eligibility="INELIGIBLE",
        confidence=0.0,
        score=0.0,
        rank_value=0.0,
        eligible_for_comparison=False,
        outcome_reason="INELIGIBLE",
        parent_decision="NO_TRADE",
        parent_selected=False,
    )
    value = build(
        prediction=prediction,
        observations=(
            observation(
                prediction=prediction,
                option_premium=None,
            ),
        ),
    )

    assert value.entry_occurred is False
    assert value.highest_option_premium is None
    assert value.lowest_option_premium is None


def test_sequence_gaps_duplicates_and_identity_fail_closed():
    prediction = record()
    first = observation(
        prediction=prediction,
        sequence_number=1,
    )

    with pytest.raises(
        ValueError,
        match="contiguous",
    ):
        build(
            prediction=prediction,
            observations=(
                first,
                observation(
                    prediction=prediction,
                    sequence_number=3,
                    seconds=60,
                ),
            ),
        )

    with pytest.raises(
        ValueError,
        match="duplicate observation_id",
    ):
        build(
            prediction=prediction,
            observations=(
                first,
                replace(
                    observation(
                        prediction=prediction,
                        sequence_number=2,
                        seconds=60,
                    ),
                    observation_id=first.observation_id,
                ),
            ),
        )

    with pytest.raises(
        ValueError,
        match="identity mismatch",
    ):
        build(
            prediction=prediction,
            observations=(
                replace(
                    first,
                    prediction_id="other-prediction",
                ),
            ),
        )


def test_timestamp_entry_window_and_validity_fail_closed():
    prediction = record()

    with pytest.raises(
        ValueError,
        match="within_entry_window mismatch",
    ):
        build(
            prediction=prediction,
            observations=(
                observation(
                    prediction=prediction,
                    seconds=30,
                    within_entry_window=False,
                ),
            ),
        )

    with pytest.raises(
        ValueError,
        match="exceeds validity",
    ):
        build(
            prediction=prediction,
            observations=(
                observation(
                    prediction=prediction,
                    seconds=901,
                    within_entry_window=False,
                ),
            ),
        )


def test_no_observation_can_follow_terminal_event():
    prediction = record()
    stop = observation(
        prediction=prediction,
        sequence_number=1,
        seconds=60,
        event_type="STOP",
    )
    later = observation(
        prediction=prediction,
        sequence_number=2,
        seconds=90,
    )

    with pytest.raises(
        ValueError,
        match="follow terminal event",
    ):
        build(
            prediction=prediction,
            observations=(stop, later),
        )
