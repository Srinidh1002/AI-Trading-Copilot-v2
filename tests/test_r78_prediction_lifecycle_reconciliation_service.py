from dataclasses import FrozenInstanceError, replace
from datetime import timedelta

import pytest

from services.contracts import (
    PaperTradePositionEvaluationInputV1,
)
from services.contracts.prediction_lifecycle_outcome_record_v1 import (
    PredictionLifecycleOutcomeRecordV1,
)
from services.paper_trading import (
    evaluate_open_paper_trade_position,
)
from services.prediction_outcomes.prediction_lifecycle_reconciliation_service import (
    reconcile_prediction_lifecycle,
)
from test_r51_prediction_record_v1 import record
from tests.p7_fixture_helpers import (
    NOW,
    make_observation,
    make_open_position,
    make_open_state,
    make_policy,
)


def prediction(**changes):
    values = dict(
        requested_at=NOW - timedelta(minutes=2),
        completed_at=NOW - timedelta(minutes=1),
        market_timestamp=NOW - timedelta(minutes=1),
        received_at=NOW - timedelta(minutes=1),
        start_underlying_price=24000.0,
    )
    values.update(changes)
    return record(**values)


def lifecycle_outcome(
    prediction_value,
    *,
    outcome="STOP_HIT",
    evaluation_status="RESOLVED",
    entry_occurred=True,
    entry_at=NOW,
    entry_premium=101.0,
    highest_target_reached=0,
    terminal_event_type="STOP",
    terminal_event_at=NOW,
    terminal_option_premium=90.0,
    blockers=(),
):
    return PredictionLifecycleOutcomeRecordV1(
        outcome_id=(
            f"lifecycle-outcome:"
            f"{prediction_value.prediction_id}:{outcome}"
        ),
        prediction_id=prediction_value.prediction_id,
        parent_cycle_id=prediction_value.parent_cycle_id,
        decision_result_id=(
            prediction_value.decision_result_id
        ),
        window_id=(
            f"window:{prediction_value.prediction_id}"
        ),
        underlying_symbol=(
            prediction_value.underlying_symbol
        ),
        exchange=prediction_value.exchange,
        predicted_action=(
            prediction_value.predicted_action
        ),
        policy_id="prediction-lifecycle-policy",
        policy_version="1.0",
        evaluated_at=NOW,
        evaluation_status=evaluation_status,
        outcome=outcome,
        entry_occurred=entry_occurred,
        entry_at=entry_at,
        entry_premium=entry_premium,
        highest_target_reached=(
            highest_target_reached
        ),
        terminal_event_type=terminal_event_type,
        terminal_event_at=terminal_event_at,
        terminal_option_premium=(
            terminal_option_premium
        ),
        maximum_up_move_percent=0.1,
        maximum_down_move_percent=0.5,
        maximum_absolute_move_percent=0.5,
        evidence_observation_ids=("obs-1",),
        blockers=blockers,
    )


def terminal_position(
    *,
    option_price=90.0,
    invalidation=False,
):
    observation = make_observation(
        option_last_price=option_price,
        option_open=option_price,
        option_low=option_price - 1.0,
        option_high=option_price + 1.0,
        option_close=option_price,
    )
    values = dict(
        position=make_open_position(),
        lifecycle_policy=make_policy(
            allow_partial_exits=True
        ),
        lifecycle_state=make_open_state(),
        observation=observation,
        evaluation_timestamp=NOW,
        requested_transition_id="transition-r78",
        resulting_lifecycle_state_id="state-r78",
        evaluation_result_id="result-r78",
        exit_fill_ids=("exit-r78-1",),
        pnl_evidence_id="pnl-r78",
    )
    if invalidation:
        values.update(
            invalidation_status="TRIGGERED",
            invalidation_reason_code=(
                "PREDICTION_INVALIDATED"
            ),
        )
    result = evaluate_open_paper_trade_position(
        PaperTradePositionEvaluationInputV1(
            **values
        )
    )
    return result.resulting_position


def test_stop_position_reconciles_exactly_and_is_immutable():
    prediction_value = prediction()
    position = terminal_position()
    outcome = lifecycle_outcome(
        prediction_value,
        terminal_event_at=position.exit_fills[-1].filled_at,
        terminal_option_premium=(
            position.exit_fills[-1].fill_price
        ),
    )

    first = reconcile_prediction_lifecycle(
        prediction=prediction_value,
        outcome=outcome,
        position=position,
        reconciled_at=NOW,
    )
    second = reconcile_prediction_lifecycle(
        prediction=prediction_value,
        outcome=outcome,
        position=position,
        reconciled_at=NOW,
    )

    assert first == second
    assert first.status == "RECONCILED"
    assert first.counting_eligible is True
    assert first.entry_matches is True
    assert first.terminal_matches is True
    assert first.fill_sequence_matches is True
    assert first.quantity_matches is True
    assert first.pnl_matches is True
    assert len(first.semantic_hash) == 64

    with pytest.raises(FrozenInstanceError):
        first.status = "BLOCKED"


def test_unresolved_open_position_remains_pending():
    prediction_value = prediction()
    position = make_open_position()
    outcome = lifecycle_outcome(
        prediction_value,
        outcome="UNRESOLVED",
        evaluation_status="UNRESOLVED",
        terminal_event_type=None,
        terminal_event_at=None,
        terminal_option_premium=None,
        blockers=("OPEN_POSITION_HAS_NO_TERMINAL_EVIDENCE",),
    )

    result = reconcile_prediction_lifecycle(
        prediction=prediction_value,
        outcome=outcome,
        position=position,
        reconciled_at=NOW,
    )

    assert result.status == "PENDING"
    assert result.counting_eligible is False
    assert result.entry_matches is True


def test_no_entry_terminal_outcome_reconciles_without_position():
    prediction_value = prediction()
    outcome = lifecycle_outcome(
        prediction_value,
        outcome="EXPIRED_WITHOUT_ENTRY",
        entry_occurred=False,
        entry_at=None,
        entry_premium=None,
        terminal_event_type="VALIDITY_WINDOW_END",
        terminal_event_at=NOW,
        terminal_option_premium=None,
    )

    result = reconcile_prediction_lifecycle(
        prediction=prediction_value,
        outcome=outcome,
        position=None,
        reconciled_at=NOW,
    )

    assert result.status == "RECONCILED"
    assert result.position_id is None
    assert result.counting_eligible is True


def test_wait_no_trade_reconciles_without_position():
    prediction_value = prediction(
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
    outcome = lifecycle_outcome(
        prediction_value,
        outcome="NO_TRADE_CORRECT",
        entry_occurred=False,
        entry_at=None,
        entry_premium=None,
        terminal_event_type="VALIDITY_WINDOW_END",
        terminal_event_at=NOW,
        terminal_option_premium=None,
    )

    result = reconcile_prediction_lifecycle(
        prediction=prediction_value,
        outcome=outcome,
        position=None,
        reconciled_at=NOW,
    )

    assert result.status == "RECONCILED"
    assert result.counting_eligible is True


def test_wait_with_position_is_blocked():
    prediction_value = prediction(
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
    outcome = lifecycle_outcome(
        prediction_value,
        outcome="NO_TRADE_CORRECT",
        entry_occurred=False,
        entry_at=None,
        entry_premium=None,
        terminal_event_type="VALIDITY_WINDOW_END",
        terminal_event_at=NOW,
        terminal_option_premium=None,
    )

    result = reconcile_prediction_lifecycle(
        prediction=prediction_value,
        outcome=outcome,
        position=make_open_position(),
        reconciled_at=NOW,
    )

    assert result.status == "BLOCKED"
    assert result.blockers == (
        "WAIT_PREDICTION_CANNOT_HAVE_POSITION",
    )


def test_data_unavailable_never_becomes_counting_eligible():
    prediction_value = prediction()
    outcome = lifecycle_outcome(
        prediction_value,
        outcome="DATA_UNAVAILABLE",
        evaluation_status="DATA_UNAVAILABLE",
        entry_occurred=False,
        entry_at=None,
        entry_premium=None,
        terminal_event_type=None,
        terminal_event_at=None,
        terminal_option_premium=None,
        blockers=("OBSERVATION_WINDOW_CONTAINS_DATA_GAP",),
    )

    result = reconcile_prediction_lifecycle(
        prediction=prediction_value,
        outcome=outcome,
        position=None,
        reconciled_at=NOW,
    )

    assert result.status == "DATA_UNAVAILABLE"
    assert result.reconciliation_complete is False
    assert result.counting_eligible is False


def test_target_outcome_cannot_match_stop_only_position():
    prediction_value = prediction()
    position = terminal_position()
    outcome = lifecycle_outcome(
        prediction_value,
        outcome="T1_HIT",
        highest_target_reached=1,
        terminal_event_at=position.exit_fills[-1].filled_at,
        terminal_option_premium=(
            position.exit_fills[-1].fill_price
        ),
    )

    result = reconcile_prediction_lifecycle(
        prediction=prediction_value,
        outcome=outcome,
        position=position,
        reconciled_at=NOW,
    )

    assert result.status == "BLOCKED"
    assert "TERMINAL_OUTCOME_MISMATCH" in (
        result.blockers
    )


def test_entry_timestamp_or_premium_mismatch_blocks():
    prediction_value = prediction()
    position = terminal_position()
    outcome = lifecycle_outcome(
        prediction_value,
        entry_at=NOW + timedelta(seconds=1),
        terminal_event_at=position.exit_fills[-1].filled_at,
        terminal_option_premium=(
            position.exit_fills[-1].fill_price
        ),
    )

    result = reconcile_prediction_lifecycle(
        prediction=prediction_value,
        outcome=outcome,
        position=position,
        reconciled_at=NOW,
    )

    assert result.status == "BLOCKED"
    assert "ENTRY_EVIDENCE_MISMATCH" in result.blockers


def test_pnl_is_recomputed_from_fills_and_charges():
    prediction_value = prediction()
    position = terminal_position()
    corrupted = replace(
        position,
        realized_gross_pnl=(
            position.realized_gross_pnl + 1.0
        ),
        realized_net_pnl=(
            position.realized_net_pnl + 1.0
        ),
        total_pnl=position.total_pnl + 1.0,
    )
    outcome = lifecycle_outcome(
        prediction_value,
        terminal_event_at=corrupted.exit_fills[-1].filled_at,
        terminal_option_premium=(
            corrupted.exit_fills[-1].fill_price
        ),
    )

    result = reconcile_prediction_lifecycle(
        prediction=prediction_value,
        outcome=outcome,
        position=corrupted,
        reconciled_at=NOW,
    )

    assert result.status == "BLOCKED"
    assert result.pnl_matches is False
    assert "PNL_MISMATCH" in result.blockers


def test_prediction_outcome_identity_mismatch_fails_closed():
    prediction_value = prediction()
    outcome = lifecycle_outcome(prediction_value)
    mismatched = replace(
        outcome,
        prediction_id="different-prediction",
    )

    result = reconcile_prediction_lifecycle(
        prediction=prediction_value,
        outcome=mismatched,
        position=None,
        reconciled_at=NOW,
    )

    assert result.status == "BLOCKED"
    assert result.identity_matches is False
    assert result.blockers == (
        "PREDICTION_OUTCOME_IDENTITY_MISMATCH",
    )

