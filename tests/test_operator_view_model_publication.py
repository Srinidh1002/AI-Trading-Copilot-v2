"""Task 6 Slice 7 operator dashboard publication certification."""
from datetime import datetime, timezone

import pytest

from dashboard.dashboard_publication_sync import (
    OPERATOR_APPLICATION_VIEW_MODEL_SEQUENCE_STATE_KEY,
    OPERATOR_APPLICATION_VIEW_MODEL_STATE_KEY,
    synchronize_operator_view_model_publication,
)
from services.contracts.operator_application_view_model_v1 import (
    OperatorActiveTradeCardV1,
    OperatorApplicationViewModelV1,
    OperatorCapitalCardV1,
    OperatorHealthCardV1,
    OperatorMarketCardV1,
    OperatorRecommendationCardV1,
)


NOW = datetime(2026, 8, 3, 10, 50, tzinfo=timezone.utc)


def market_card(name, exchange):
    return OperatorMarketCardV1(
        title=name,
        exchange=exchange,
        score_label="Score: 0.75",
        confidence_label="Confidence: 80%",
        direction_label="Direction: BULLISH",
        eligibility_label="Eligibility: ELIGIBLE",
        freshness_label="Data: FRESH",
        reasons=("TREND_ALIGNED",),
        rejection_reasons=(),
    )


def view_model(view_id="view-1"):
    return OperatorApplicationViewModelV1(
        view_model_id=view_id,
        generated_at=NOW,
        title="AI Trading Copilot",
        subtitle="NIFTY and SENSEX certified operator view",
        selected_market_banner="Selected market: NIFTY",
        losing_market_banner="Losing market: SENSEX | LOWER_SCORE",
        nifty_card=market_card("NIFTY", "NSE"),
        sensex_card=market_card("SENSEX", "BSE"),
        recommendation_card=OperatorRecommendationCardV1(
            action_label="Action: CALL",
            selected_market_label="Market: NIFTY",
            contract_label="Contract: NIFTY06AUG26C25000",
            entry_label="Entry: 100.00",
            stop_label="Stop: 90.00",
            targets_label="Targets: T1 110.00 | T2 120.00 | T3 130.00",
            confidence_label="Confidence: 82%",
            explanation=("NIFTY_OUTRANKED_SENSEX",),
        ),
        capital_card=OperatorCapitalCardV1(
            supplied_capital_label="Supplied capital: ₹100,000.00",
            usable_capital_label="Usable capital: ₹90,000.00",
            position_size_label="Position size: 2 lots / 50 quantity",
            capital_required_label="Capital required: ₹5,050.00",
            maximum_loss_label="Maximum loss: ₹1,000.00",
            daily_risk_used_label="Daily risk used: ₹1,000.00",
        ),
        active_trade_card=OperatorActiveTradeCardV1(
            status_label="Active trade: YES",
            contract_label="Contract: NIFTY06AUG26C25000",
            premium_label="Current premium: 105.00",
            pnl_label="Unrealized P&L: ₹250.00",
            target_status_label="Target status: T1_PENDING",
            stop_status_label="Stop status: ORIGINAL_STOP",
            instruction_label="Instruction: HOLD",
            confidence_warning_label="Confidence warning: STABLE",
        ),
        health_card=OperatorHealthCardV1(
            status_label="System status: HEALTHY",
            data_freshness_label="Data freshness: FRESH",
            data_connection_label="Data connection: CONNECTED",
            broker_connection_label="Broker connection: ISOLATED",
            mode_label="Mode: PAPER",
            broker_submission_label="Broker submission: DISABLED",
            emergency_halt_label="Emergency halt: CLEAR",
            runtime_label="Runtime: HEALTHY",
            journal_label="Journal: HEALTHY",
            warnings=(),
        ),
        read_only_notice="Read-only operator view. No broker order submission.",
    )


def test_new_operator_publication_is_applied():
    state = {}
    model = view_model()

    applied = synchronize_operator_view_model_publication(
        state,
        publication_sequence=1,
        view_model=model,
    )

    assert applied is True
    assert state[OPERATOR_APPLICATION_VIEW_MODEL_STATE_KEY] is model
    assert (
        state[OPERATOR_APPLICATION_VIEW_MODEL_SEQUENCE_STATE_KEY]
        == 1
    )


def test_same_or_older_sequence_is_ignored_without_clearing():
    original = view_model("view-1")
    state = {
        OPERATOR_APPLICATION_VIEW_MODEL_STATE_KEY: original,
        OPERATOR_APPLICATION_VIEW_MODEL_SEQUENCE_STATE_KEY: 5,
    }

    assert (
        synchronize_operator_view_model_publication(
            state,
            publication_sequence=5,
            view_model=view_model("view-2"),
        )
        is False
    )
    assert state[OPERATOR_APPLICATION_VIEW_MODEL_STATE_KEY] is original


def test_newer_sequence_replaces_operator_view():
    original = view_model("view-1")
    replacement = view_model("view-2")
    state = {
        OPERATOR_APPLICATION_VIEW_MODEL_STATE_KEY: original,
        OPERATOR_APPLICATION_VIEW_MODEL_SEQUENCE_STATE_KEY: 5,
    }

    applied = synchronize_operator_view_model_publication(
        state,
        publication_sequence=6,
        view_model=replacement,
    )

    assert applied is True
    assert state[OPERATOR_APPLICATION_VIEW_MODEL_STATE_KEY] is replacement


def test_invalid_view_model_fails_closed():
    with pytest.raises(TypeError, match="exact"):
        synchronize_operator_view_model_publication(
            {},
            publication_sequence=1,
            view_model=object(),
        )


@pytest.mark.parametrize("sequence", [0, -1, True, 1.5])
def test_invalid_sequence_fails_closed(sequence):
    with pytest.raises(ValueError, match="publication_sequence"):
        synchronize_operator_view_model_publication(
            {},
            publication_sequence=sequence,
            view_model=view_model(),
        )


def test_corrupt_existing_sequence_fails_closed():
    state = {
        OPERATOR_APPLICATION_VIEW_MODEL_SEQUENCE_STATE_KEY: "bad",
    }

    with pytest.raises(TypeError, match="exact int"):
        synchronize_operator_view_model_publication(
            state,
            publication_sequence=2,
            view_model=view_model(),
        )
