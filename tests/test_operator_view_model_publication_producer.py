"""Task 6 Slice 8 automatic operator production/publication certification."""
from datetime import datetime, timezone

import pytest

from dashboard.dashboard_publication_sync import (
    OPERATOR_APPLICATION_VIEW_MODEL_SEQUENCE_STATE_KEY,
    OPERATOR_APPLICATION_VIEW_MODEL_STATE_KEY,
)
from services.contracts.operator_application_snapshot_v1 import (
    OperatorActiveTradeStateV1,
    OperatorCapitalStateV1,
    OperatorMarketStateV1,
    OperatorRecommendationStateV1,
    OperatorSystemHealthV1,
)
from services.contracts.operator_snapshot_runtime_input_v1 import (
    OperatorSnapshotRuntimeInputV1,
)
from services.operator.operator_view_model_publication_producer import (
    produce_and_publish_operator_view_model,
)


NOW = datetime(2026, 8, 3, 10, 55, tzinfo=timezone.utc)


def market(name, exchange, **changes):
    values = dict(
        market=name,
        exchange=exchange,
        score=0.75,
        confidence=0.8,
        eligible=True,
        direction="BULLISH",
        data_fresh=True,
        reasons=("TREND_ALIGNED",),
        rejection_reasons=(),
    )
    values.update(changes)
    return OperatorMarketStateV1(**values)


def recommendation(**changes):
    values = dict(
        action="CALL",
        selected_market="NIFTY",
        contract="NIFTY06AUG26C25000",
        entry_price=100.0,
        stop_loss=90.0,
        target_1=110.0,
        target_2=120.0,
        target_3=130.0,
        confidence=0.82,
        explanation=("NIFTY_OUTRANKED_SENSEX",),
    )
    values.update(changes)
    return OperatorRecommendationStateV1(**values)


def runtime_input(**changes):
    values = dict(
        runtime_input_id="runtime-input-1",
        generated_at=NOW,
        nifty=market("NIFTY", "NSE"),
        sensex=market(
            "SENSEX",
            "BSE",
            score=0.35,
            confidence=0.5,
            eligible=False,
            direction="NEUTRAL",
            rejection_reasons=("LOW_CONFIDENCE",),
        ),
        recommendation=recommendation(),
        capital=OperatorCapitalStateV1(
            supplied_capital=100000.0,
            usable_capital=90000.0,
            lots=2,
            quantity=50,
            capital_required=5050.0,
            maximum_loss=1000.0,
            daily_risk_used=1000.0,
        ),
        active_trade=OperatorActiveTradeStateV1(
            active=True,
            contract="NIFTY06AUG26C25000",
            current_premium=105.0,
            unrealized_pnl=250.0,
            target_status="T1_PENDING",
            stop_status="ORIGINAL_STOP",
            instruction="HOLD",
            confidence_deteriorating=False,
        ),
        system_health=OperatorSystemHealthV1(
            status="HEALTHY",
            data_fresh=True,
            data_connection="CONNECTED",
            broker_connection="ISOLATED",
            mode="PAPER",
            broker_submission_enabled=False,
            emergency_halt=False,
            runtime_healthy=True,
            journal_healthy=True,
        ),
    )
    values.update(changes)
    return OperatorSnapshotRuntimeInputV1(**values)


def produce(state, **changes):
    values = dict(
        publication_sequence=1,
        snapshot_id="snapshot-1",
        view_model_id="view-1",
        runtime_input=runtime_input(),
        dashboard_state=state,
    )
    values.update(changes)
    return produce_and_publish_operator_view_model(**values)


def test_producer_runs_full_pipeline_and_publishes():
    state = {}

    result = produce(state)

    assert result.view_model_id == "view-1"
    assert result.selected_market_banner == "Selected market: NIFTY"
    assert state[OPERATOR_APPLICATION_VIEW_MODEL_STATE_KEY] is result
    assert (
        state[OPERATOR_APPLICATION_VIEW_MODEL_SEQUENCE_STATE_KEY]
        == 1
    )


def test_newer_publication_replaces_prior_view():
    state = {}
    first = produce(state)
    second = produce(
        state,
        publication_sequence=2,
        snapshot_id="snapshot-2",
        view_model_id="view-2",
    )

    assert first.view_model_id == "view-1"
    assert second.view_model_id == "view-2"
    assert state[OPERATOR_APPLICATION_VIEW_MODEL_STATE_KEY] is second


def test_duplicate_sequence_preserves_last_known_good():
    state = {}
    first = produce(state)

    second = produce(
        state,
        publication_sequence=1,
        snapshot_id="snapshot-2",
        view_model_id="view-2",
    )

    assert second.view_model_id == "view-2"
    assert state[OPERATOR_APPLICATION_VIEW_MODEL_STATE_KEY] is first
    assert (
        state[OPERATOR_APPLICATION_VIEW_MODEL_SEQUENCE_STATE_KEY]
        == 1
    )


def test_wait_pipeline_publishes_non_executable_view():
    state = {}
    wait = recommendation(
        action="WAIT",
        selected_market=None,
        contract=None,
        entry_price=None,
        stop_loss=None,
        target_1=None,
        target_2=None,
        target_3=None,
    )
    inactive = OperatorActiveTradeStateV1(
        active=False,
        contract=None,
        current_premium=None,
        unrealized_pnl=0.0,
        target_status="NONE",
        stop_status="NONE",
        instruction="NONE",
        confidence_deteriorating=False,
    )

    result = produce(
        state,
        runtime_input=runtime_input(
            recommendation=wait,
            active_trade=inactive,
        ),
    )

    assert result.selected_market_banner == "Selected market: NONE"
    assert result.recommendation_card.entry_label == "Entry: N/A"


def test_invalid_runtime_input_fails_before_publication():
    state = {}

    with pytest.raises(TypeError, match="runtime_input"):
        produce_and_publish_operator_view_model(
            publication_sequence=1,
            snapshot_id="snapshot-1",
            view_model_id="view-1",
            runtime_input=object(),
            dashboard_state=state,
        )

    assert state == {}


def test_invalid_state_fails_before_pipeline():
    with pytest.raises(TypeError, match="dashboard_state"):
        produce_and_publish_operator_view_model(
            publication_sequence=1,
            snapshot_id="snapshot-1",
            view_model_id="view-1",
            runtime_input=runtime_input(),
            dashboard_state=object(),
        )
