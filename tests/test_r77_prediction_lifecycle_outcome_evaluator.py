from dataclasses import FrozenInstanceError, replace
from datetime import timedelta

import pytest

from services.contracts.prediction_lifecycle_outcome_input_v1 import (
    PredictionLifecycleOutcomeInputV1,
)
from services.contracts.prediction_lifecycle_outcome_policy_v1 import (
    PredictionLifecycleOutcomePolicyV1,
)
from services.contracts.prediction_observation_v1 import PredictionObservationV1
from services.prediction_outcomes.prediction_lifecycle_outcome_evaluator import (
    evaluate_prediction_lifecycle_outcome,
)
from services.prediction_outcomes.prediction_observation_window_tracker import (
    build_prediction_observation_window,
)
from test_r51_prediction_record_v1 import record


def policy(**changes):
    values = {
        "policy_id": "prediction-lifecycle-policy",
        "policy_version": "1.0",
    }
    values.update(changes)
    return PredictionLifecycleOutcomePolicyV1(**values)


def obs(
    prediction,
    sequence,
    seconds,
    event,
    *,
    option=100.0,
    underlying=25000.0,
    available=True,
):
    return PredictionObservationV1(
        observation_id=f"obs-{sequence}",
        prediction_id=prediction.prediction_id,
        parent_cycle_id=prediction.parent_cycle_id,
        underlying_symbol=prediction.underlying_symbol,
        exchange=prediction.exchange,
        sequence_number=sequence,
        observed_at=prediction.completed_at + timedelta(seconds=seconds),
        underlying_price=underlying if available else None,
        option_premium=option if available else None,
        event_type=event,
        within_entry_window=available and seconds <= 300,
        data_available=available,
    )


def evaluate(
    prediction,
    observations,
    *,
    evaluated_seconds=900,
    selected_policy=None,
):
    window = build_prediction_observation_window(
        prediction=prediction,
        observations=observations,
        entry_window_ends_at=prediction.completed_at + timedelta(minutes=5),
        validity_window_ends_at=prediction.completed_at + timedelta(minutes=15),
    )
    return evaluate_prediction_lifecycle_outcome(
        PredictionLifecycleOutcomeInputV1(
            prediction=prediction,
            observation_window=window,
            policy=selected_policy or policy(),
            evaluated_at=prediction.completed_at
            + timedelta(seconds=evaluated_seconds),
        )
    )


def test_policy_and_outcome_are_immutable_and_deterministic():
    prediction = record()
    observations = (
        obs(prediction, 1, 30, "ENTRY"),
        obs(prediction, 2, 60, "T1", option=120.0),
        obs(prediction, 3, 90, "STOP", option=90.0),
    )
    first = evaluate(prediction, observations)
    second = evaluate(prediction, observations)

    assert first == second
    assert first.to_json() == second.to_json()
    assert len(first.semantic_hash) == 64
    assert len(policy().semantic_hash) == 64
    with pytest.raises(FrozenInstanceError):
        first.outcome = "STOP_HIT"


def test_partial_target_before_later_stop_keeps_highest_target():
    prediction = record()
    result = evaluate(
        prediction,
        (
            obs(prediction, 1, 30, "ENTRY"),
            obs(prediction, 2, 60, "T1", option=120.0),
            obs(prediction, 3, 90, "STOP", option=90.0),
        ),
    )
    assert result.outcome == "T1_HIT"
    assert result.highest_target_reached == 1
    assert result.terminal_event_type == "STOP"


def test_same_timestamp_stop_first_is_order_independent():
    prediction = record()
    entry = obs(prediction, 1, 30, "ENTRY")
    target = obs(prediction, 2, 60, "T1", option=120.0)
    stop = obs(prediction, 3, 60, "STOP", option=90.0)

    first = evaluate(prediction, (entry, target, stop))
    second = evaluate(
        prediction,
        (
            entry,
            replace(stop, sequence_number=2),
            replace(target, sequence_number=3),
        ),
    )
    assert first.outcome == "STOP_HIT"
    assert second.outcome == "STOP_HIT"


def test_target_first_credits_highest_same_timestamp_target():
    prediction = record()
    result = evaluate(
        prediction,
        (
            obs(prediction, 1, 30, "ENTRY"),
            obs(prediction, 2, 60, "STOP", option=90.0),
            obs(prediction, 3, 60, "T2", option=130.0),
        ),
        selected_policy=policy(same_observation_precedence="TARGET_FIRST"),
    )
    assert result.outcome == "T2_HIT"
    assert result.highest_target_reached == 2


def test_multiple_targets_at_one_timestamp_use_highest_crossed():
    prediction = record()
    result = evaluate(
        prediction,
        (
            obs(prediction, 1, 30, "ENTRY"),
            obs(prediction, 2, 60, "T1", option=120.0),
            obs(prediction, 3, 60, "T2", option=140.0),
            obs(prediction, 4, 60, "T3", option=160.0),
        ),
    )
    assert result.outcome == "T3_HIT"
    assert result.highest_target_reached == 3


@pytest.mark.parametrize(
    ("premium", "expected"),
    (
        (110.0, "EARLY_EXIT_PROFIT"),
        (100.0, "EARLY_EXIT_LOSS"),
        (90.0, "EARLY_EXIT_LOSS"),
    ),
)
def test_early_exit_profit_loss_and_break_even(premium, expected):
    prediction = record()
    result = evaluate(
        prediction,
        (
            obs(prediction, 1, 30, "ENTRY"),
            obs(prediction, 2, 90, "EARLY_EXIT", option=premium),
        ),
    )
    assert result.outcome == expected


def test_invalidated_and_expired_without_entry():
    prediction = record()
    invalidated = evaluate(
        prediction,
        (obs(prediction, 1, 120, "INVALIDATED", option=None),),
        evaluated_seconds=120,
    )
    assert invalidated.outcome == "INVALIDATED_BEFORE_ENTRY"

    expired = evaluate(
        prediction,
        (obs(prediction, 1, 900, "EXPIRY", option=None),),
    )
    assert expired.outcome == "EXPIRED_WITHOUT_ENTRY"


def test_data_gap_fails_closed():
    prediction = record()
    result = evaluate(
        prediction,
        (
            obs(
                prediction,
                1,
                30,
                "DATA_GAP",
                option=None,
                underlying=None,
                available=False,
            ),
        ),
    )
    assert result.evaluation_status == "DATA_UNAVAILABLE"
    assert result.outcome == "DATA_UNAVAILABLE"


@pytest.mark.parametrize(
    ("high", "low", "expected"),
    (
        (25020.0, 24990.0, "NO_TRADE_CORRECT"),
        (25060.0, 24990.0, "NO_TRADE_MISSED_MOVE"),
    ),
)
def test_wait_and_no_trade_missed_move_policy(high, low, expected):
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
    result = evaluate(
        prediction,
        (
            obs(prediction, 1, 60, "NONE", option=None, underlying=high),
            obs(
                prediction,
                2,
                900,
                "SESSION_CLOSE",
                option=None,
                underlying=low,
            ),
        ),
    )
    assert result.outcome == expected
    assert result.entry_occurred is False


def test_open_entry_without_terminal_evidence_remains_unresolved():
    prediction = record()
    result = evaluate(
        prediction,
        (
            obs(prediction, 1, 30, "ENTRY"),
            obs(prediction, 2, 60, "NONE", option=110.0),
        ),
        evaluated_seconds=60,
    )
    assert result.evaluation_status == "UNRESOLVED"
    assert result.outcome == "UNRESOLVED"
