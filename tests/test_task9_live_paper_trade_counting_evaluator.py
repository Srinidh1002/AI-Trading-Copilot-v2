from dataclasses import replace
from datetime import timedelta

import pytest

from services.certification.task9_live_paper_trade_counting_evaluator import (
    evaluate_task9_live_paper_trade_counting,
)
from services.contracts import (
    PaperTradePositionEvaluationInputV1,
)
from services.contracts.prediction_lifecycle_outcome_record_v1 import (
    PredictionLifecycleOutcomeRecordV1,
)
from services.contracts.task9_live_paper_trade_counting_input_v1 import (
    Task9LivePaperTradeCountingInputV1,
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


RUN_ID = "task9-live-run-1"


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


def no_trade_prediction(**changes):
    values = dict(
        predicted_direction="NEUTRAL",
        predicted_action="NO_TRADE",
        eligibility="INELIGIBLE",
        confidence=0.0,
        score=0.0,
        rank_value=0.0,
        eligible_for_comparison=False,
        outcome_reason="INELIGIBLE",
        parent_decision="NO_TRADE",
        parent_selected=False,
    )
    values.update(changes)
    return prediction(**values)


def wait_prediction(**changes):
    return no_trade_prediction(predicted_action="WAIT", **changes)


def lifecycle_outcome(
    prediction_value,
    *,
    outcome="EARLY_EXIT_LOSS",
    evaluation_status="RESOLVED",
    entry_occurred=True,
    entry_at=NOW,
    entry_premium=101.0,
    terminal_event_type="EARLY_EXIT",
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
        decision_result_id=prediction_value.decision_result_id,
        window_id=f"window:{prediction_value.prediction_id}",
        underlying_symbol=prediction_value.underlying_symbol,
        exchange=prediction_value.exchange,
        predicted_action=prediction_value.predicted_action,
        policy_id="prediction-lifecycle-policy",
        policy_version="1.0",
        evaluated_at=NOW,
        evaluation_status=evaluation_status,
        outcome=outcome,
        entry_occurred=entry_occurred,
        entry_at=entry_at if entry_occurred else None,
        entry_premium=entry_premium if entry_occurred else None,
        highest_target_reached=0,
        terminal_event_type=terminal_event_type,
        terminal_event_at=terminal_event_at,
        terminal_option_premium=terminal_option_premium,
        maximum_up_move_percent=0.1,
        maximum_down_move_percent=0.5,
        maximum_absolute_move_percent=0.5,
        evidence_observation_ids=("obs-task9",),
        blockers=blockers,
    )


def counting_input(
    *,
    prediction_value,
    lifecycle_outcome_value,
    reconciliation_value,
    **changes,
):
    values = dict(
        prediction=prediction_value,
        lifecycle_outcome=lifecycle_outcome_value,
        reconciliation=reconciliation_value,
        record_source="LIVE_REAL_TIME",
        session_status="REAL_TIME_MARKET_SESSION",
        evidence_status="VALID",
        official_run_id=RUN_ID,
        record_run_id=RUN_ID,
        official_start_at=prediction_value.completed_at - timedelta(seconds=1),
        evaluated_at=NOW,
    )
    values.update(changes)
    return Task9LivePaperTradeCountingInputV1(**values)


def terminal_position():
    observation = make_observation(
        option_last_price=90.0,
        option_open=90.0,
        option_low=89.0,
        option_high=91.0,
        option_close=90.0,
    )

    result = evaluate_open_paper_trade_position(
        PaperTradePositionEvaluationInputV1(
            position=make_open_position(),
            lifecycle_policy=make_policy(
                allow_partial_exits=True,
            ),
            lifecycle_state=make_open_state(),
            observation=observation,
            evaluation_timestamp=NOW,
            requested_transition_id="transition-task9",
            resulting_lifecycle_state_id="state-task9",
            evaluation_result_id="result-task9",
            exit_fill_ids=("exit-task9-1",),
            pnl_evidence_id="pnl-task9",
        )
    )

    return result.resulting_position


def resolved_no_trade_decision(outcome_name):
    prediction_value = no_trade_prediction()

    outcome_value = lifecycle_outcome(
        prediction_value,
        outcome=outcome_name,
        entry_occurred=False,
        entry_at=None,
        entry_premium=None,
        terminal_event_type=None,
        terminal_event_at=None,
        terminal_option_premium=None,
    )

    return evaluate_task9_live_paper_trade_counting(
        counting_input(
            prediction_value=prediction_value,
            lifecycle_outcome_value=outcome_value,
            reconciliation_value=None,
        )
    )


def test_no_trade_without_later_outcome_remains_pending():
    prediction_value = no_trade_prediction()

    decision = evaluate_task9_live_paper_trade_counting(
        counting_input(
            prediction_value=prediction_value,
            lifecycle_outcome_value=None,
            reconciliation_value=None,
        )
    )

    assert decision.status == "PENDING"
    assert decision.pending is True
    assert decision.no_trade_record is False
    assert decision.trade_target_countable is False


def test_no_trade_correct_becomes_completed_pass_analytics_only():
    decision = resolved_no_trade_decision(
        "NO_TRADE_CORRECT"
    )

    assert decision.status == "NO_TRADE"
    assert decision.trade_target_countable is False
    assert decision.no_trade_record is True
    assert decision.pending is False
    assert decision.reason_codes == (
        "NO_TRADE_CORRECT_RECORDED_SEPARATELY",
    )


def test_no_trade_missed_move_becomes_completed_fail_analytics_only():
    decision = resolved_no_trade_decision(
        "NO_TRADE_MISSED_MOVE"
    )

    assert decision.status == "NO_TRADE"
    assert decision.trade_target_countable is False
    assert decision.no_trade_record is True
    assert decision.pending is False
    assert decision.reason_codes == (
        "NO_TRADE_MISSED_MOVE_RECORDED_SEPARATELY",
    )


def test_wait_without_later_outcome_remains_pending():
    prediction_value = wait_prediction()

    decision = evaluate_task9_live_paper_trade_counting(
        counting_input(
            prediction_value=prediction_value,
            lifecycle_outcome_value=None,
            reconciliation_value=None,
        )
    )

    assert decision.status == "PENDING"
    assert decision.pending is True
    assert decision.trade_target_countable is False


def test_resolved_wait_requires_no_reconciliation_and_remains_distinct_from_no_trade():
    prediction_value = wait_prediction(parent_decision="NO_TRADE")
    outcome_value = lifecycle_outcome(
        prediction_value,
        outcome="NO_TRADE_CORRECT",
        entry_occurred=False,
        entry_at=None,
        entry_premium=None,
        terminal_event_type=None,
        terminal_event_at=None,
        terminal_option_premium=None,
    )

    decision = evaluate_task9_live_paper_trade_counting(
        counting_input(
            prediction_value=prediction_value,
            lifecycle_outcome_value=outcome_value,
            reconciliation_value=None,
        )
    )

    assert decision.status == "WAIT"
    assert decision.pending is False
    assert decision.wait_record is True
    assert decision.no_trade_record is False
    assert decision.trade_target_countable is False


def test_abstention_with_paper_entry_is_rejected_by_outcome_contract():
    prediction_value = wait_prediction()
    with pytest.raises(ValueError, match="abstention action cannot contain entry"):
        lifecycle_outcome(
            prediction_value,
            outcome="NO_TRADE_CORRECT",
            entry_occurred=True,
        )


def test_abstention_data_unavailable_remains_non_countable():
    prediction_value = wait_prediction()
    unavailable = lifecycle_outcome(
        prediction_value,
        outcome="DATA_UNAVAILABLE",
        evaluation_status="DATA_UNAVAILABLE",
        entry_occurred=False,
        entry_at=None,
        entry_premium=None,
        terminal_event_type=None,
        terminal_event_at=None,
        terminal_option_premium=None,
        blockers=("UNDERLYING_EXTREMA_UNAVAILABLE",),
    )

    unavailable_decision = evaluate_task9_live_paper_trade_counting(
        counting_input(prediction_value=prediction_value, lifecycle_outcome_value=unavailable, reconciliation_value=None)
    )

    assert unavailable_decision.status == "EXCLUDED_UNRESOLVED"
    assert unavailable_decision.pending is False
    assert unavailable_decision.trade_target_countable is False


def test_historical_provider_incident_is_excluded_from_task9_trade_target():
    prediction_value = prediction()

    decision = evaluate_task9_live_paper_trade_counting(
        counting_input(
            prediction_value=prediction_value,
            lifecycle_outcome_value=None,
            reconciliation_value=None,
            evidence_status="DATA_INCIDENT",
        )
    )

    assert decision.status == "EXCLUDED_DATA_INCIDENT"
    assert decision.trade_target_countable is False
    assert decision.reason_codes == ("DATA_INCIDENT",)


def test_replay_never_counts_toward_live_target():
    prediction_value = prediction()

    decision = evaluate_task9_live_paper_trade_counting(
        counting_input(
            prediction_value=prediction_value,
            lifecycle_outcome_value=None,
            reconciliation_value=None,
            record_source="REPLAY",
        )
    )

    assert decision.status == "EXCLUDED_REPLAY"
    assert decision.trade_target_countable is False


def test_missing_lifecycle_evidence_is_pending_not_counted():
    prediction_value = prediction()

    decision = evaluate_task9_live_paper_trade_counting(
        counting_input(
            prediction_value=prediction_value,
            lifecycle_outcome_value=None,
            reconciliation_value=None,
        )
    )

    assert decision.status == "PENDING"
    assert decision.pending is True
    assert decision.trade_target_countable is False


def test_no_entry_directional_outcome_never_counts_toward_100():
    prediction_value = prediction()

    outcome_value = lifecycle_outcome(
        prediction_value,
        outcome="EXPIRED_WITHOUT_ENTRY",
        entry_occurred=False,
        entry_at=None,
        entry_premium=None,
        terminal_event_type="EXPIRY",
        terminal_event_at=NOW,
        terminal_option_premium=90.0,
    )

    reconciliation_value = reconcile_prediction_lifecycle(
        prediction=prediction_value,
        outcome=outcome_value,
        position=None,
        reconciled_at=NOW,
    )

    decision = evaluate_task9_live_paper_trade_counting(
        counting_input(
            prediction_value=prediction_value,
            lifecycle_outcome_value=outcome_value,
            reconciliation_value=reconciliation_value,
        )
    )

    assert decision.status == "EXCLUDED_NO_ENTRY"
    assert decision.trade_target_countable is False


def test_entered_but_open_paper_trade_remains_pending():
    prediction_value = prediction()
    position = make_open_position()

    outcome_value = lifecycle_outcome(
        prediction_value,
        evaluation_status="UNRESOLVED",
        outcome="UNRESOLVED",
        entry_occurred=True,
        entry_at=position.opened_at,
        entry_premium=position.entry_price,
        terminal_event_type=None,
        terminal_event_at=None,
        terminal_option_premium=None,
        blockers=("POSITION_AND_OUTCOME_REMAIN_OPEN",),
    )

    reconciliation_value = reconcile_prediction_lifecycle(
        prediction=prediction_value,
        outcome=outcome_value,
        position=position,
        reconciled_at=NOW,
    )

    decision = evaluate_task9_live_paper_trade_counting(
        counting_input(
            prediction_value=prediction_value,
            lifecycle_outcome_value=outcome_value,
            reconciliation_value=reconciliation_value,
        )
    )

    assert decision.status == "PENDING"
    assert decision.pending is True
    assert decision.trade_target_countable is False


def test_entered_terminal_closed_reconciled_paper_trade_is_counted():
    prediction_value = prediction()
    position = terminal_position()

    outcome_value = lifecycle_outcome(
        prediction_value,
        outcome="STOP_HIT",
        entry_occurred=True,
        entry_at=position.opened_at,
        entry_premium=position.entry_price,
        terminal_event_type="STOP",
        terminal_event_at=position.exit_fills[-1].filled_at,
        terminal_option_premium=position.exit_fills[-1].fill_price,
    )

    reconciliation_value = reconcile_prediction_lifecycle(
        prediction=prediction_value,
        outcome=outcome_value,
        position=position,
        reconciled_at=NOW,
    )

    decision = evaluate_task9_live_paper_trade_counting(
        counting_input(
            prediction_value=prediction_value,
            lifecycle_outcome_value=outcome_value,
            reconciliation_value=reconciliation_value,
        )
    )

    assert reconciliation_value.status == "RECONCILED"
    assert reconciliation_value.counting_eligible is True
    assert decision.status == "COUNTED_TRADE"
    assert decision.trade_target_countable is True
    assert decision.market == "NIFTY"
    assert decision.position_id == position.position_id
    assert decision.pending is False
    assert decision.no_trade_record is False


def test_counted_trade_market_identity_is_independent():
    nifty_prediction = prediction()
    nifty_position = terminal_position()

    nifty_outcome = lifecycle_outcome(
        nifty_prediction,
        outcome="STOP_HIT",
        entry_occurred=True,
        entry_at=nifty_position.opened_at,
        entry_premium=nifty_position.entry_price,
        terminal_event_type="STOP",
        terminal_event_at=nifty_position.exit_fills[-1].filled_at,
        terminal_option_premium=nifty_position.exit_fills[-1].fill_price,
    )

    nifty_reconciliation = reconcile_prediction_lifecycle(
        prediction=nifty_prediction,
        outcome=nifty_outcome,
        position=nifty_position,
        reconciled_at=NOW,
    )

    nifty_decision = evaluate_task9_live_paper_trade_counting(
        counting_input(
            prediction_value=nifty_prediction,
            lifecycle_outcome_value=nifty_outcome,
            reconciliation_value=nifty_reconciliation,
        )
    )

    sensex_prediction = replace(
        no_trade_prediction(),
        prediction_id="prediction-task9-sensex",
        parent_cycle_id="cycle-task9-sensex",
        decision_result_id="decision-task9-sensex",
        underlying_symbol="SENSEX",
        exchange="BSE",
    )

    sensex_decision = evaluate_task9_live_paper_trade_counting(
        counting_input(
            prediction_value=sensex_prediction,
            lifecycle_outcome_value=None,
            reconciliation_value=None,
        )
    )

    assert nifty_decision.market == "NIFTY"
    assert nifty_decision.trade_target_countable is True

    assert sensex_decision.market == "SENSEX"
    assert sensex_decision.trade_target_countable is False
    assert sensex_decision.status == "PENDING"


def test_counting_decision_remains_paper_only():
    prediction_value = prediction()

    value = counting_input(
        prediction_value=prediction_value,
        lifecycle_outcome_value=None,
        reconciliation_value=None,
    )

    decision = evaluate_task9_live_paper_trade_counting(value)

    assert decision.execution_mode == "PAPER"
    assert decision.live_execution_eligible is False
    assert decision.broker_order_submission is False
    assert decision.read_only is True

