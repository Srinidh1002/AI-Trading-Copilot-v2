"""Task 6 Slice 4 operator application view-model certification."""
from datetime import datetime, timezone

import pytest

from services.contracts.operator_application_snapshot_v1 import (
    OperatorActiveTradeStateV1,
    OperatorApplicationSnapshotV1,
    OperatorCapitalStateV1,
    OperatorMarketStateV1,
    OperatorRecommendationStateV1,
    OperatorSystemHealthV1,
)
from services.operator.operator_application_view_model_projector import (
    project_operator_application_view_model,
)


NOW = datetime(2026, 8, 3, 10, 35, tzinfo=timezone.utc)


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


def capital():
    return OperatorCapitalStateV1(
        supplied_capital=100000.0,
        usable_capital=90000.0,
        lots=2,
        quantity=50,
        capital_required=5050.0,
        maximum_loss=1000.0,
        daily_risk_used=1000.0,
    )


def active_trade(**changes):
    values = dict(
        active=True,
        contract="NIFTY06AUG26C25000",
        current_premium=105.0,
        unrealized_pnl=250.0,
        target_status="T1_PENDING",
        stop_status="ORIGINAL_STOP",
        instruction="HOLD",
        confidence_deteriorating=False,
    )
    values.update(changes)
    return OperatorActiveTradeStateV1(**values)


def health(**changes):
    values = dict(
        status="HEALTHY",
        data_fresh=True,
        data_connection="CONNECTED",
        broker_connection="ISOLATED",
        mode="PAPER",
        broker_submission_enabled=False,
        emergency_halt=False,
        runtime_healthy=True,
        journal_healthy=True,
    )
    values.update(changes)
    return OperatorSystemHealthV1(**values)


def snapshot(**changes):
    values = dict(
        snapshot_id="snapshot-1",
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
        selected_market="NIFTY",
        losing_market="SENSEX",
        losing_market_reasons=(
            "LOW_CONFIDENCE",
            "LOWER_SCORE",
            "LOWER_CONFIDENCE",
        ),
        recommendation=recommendation(),
        capital=capital(),
        active_trade=active_trade(),
        system_health=health(),
    )
    values.update(changes)
    return OperatorApplicationSnapshotV1(**values)


def test_projects_complete_view_model():
    result = project_operator_application_view_model(
        view_model_id="view-1",
        snapshot=snapshot(),
    )

    assert result.title == "AI Trading Copilot"
    assert result.selected_market_banner == "Selected market: NIFTY"
    assert "SENSEX" in result.losing_market_banner
    assert result.recommendation_card.action_label == "Action: CALL"
    assert result.capital_card.maximum_loss_label == (
        "Maximum loss: ₹1,000.00"
    )
    assert result.read_only is True


def test_market_cards_preserve_reasons():
    result = project_operator_application_view_model(
        view_model_id="view-2",
        snapshot=snapshot(),
    )

    assert result.nifty_card.reasons == ("TREND_ALIGNED",)
    assert result.sensex_card.rejection_reasons == (
        "LOW_CONFIDENCE",
    )


def test_active_trade_negative_pnl_is_formatted():
    result = project_operator_application_view_model(
        view_model_id="view-3",
        snapshot=snapshot(
            active_trade=active_trade(unrealized_pnl=-250.0)
        ),
    )

    assert result.active_trade_card.pnl_label == (
        "Unrealized P&L: -₹250.00"
    )


def test_inactive_trade_is_rendered_without_fake_values():
    result = project_operator_application_view_model(
        view_model_id="view-4",
        snapshot=snapshot(
            active_trade=active_trade(
                active=False,
                contract=None,
                current_premium=None,
                unrealized_pnl=0.0,
                target_status="NONE",
                stop_status="NONE",
                instruction="NONE",
            )
        ),
    )

    assert result.active_trade_card.status_label == "Active trade: NO"
    assert result.active_trade_card.contract_label == "Contract: NONE"
    assert result.active_trade_card.premium_label == (
        "Current premium: N/A"
    )


def test_wait_recommendation_uses_na_geometry():
    result = project_operator_application_view_model(
        view_model_id="view-5",
        snapshot=snapshot(
            selected_market=None,
            losing_market=None,
            losing_market_reasons=(),
            recommendation=recommendation(
                action="WAIT",
                selected_market=None,
                contract=None,
                entry_price=None,
                stop_loss=None,
                target_1=None,
                target_2=None,
                target_3=None,
            ),
        ),
    )

    assert result.selected_market_banner == "Selected market: NONE"
    assert result.recommendation_card.entry_label == "Entry: N/A"
    assert result.recommendation_card.targets_label == "Targets: N/A"


def test_health_card_keeps_paper_safety_visible():
    result = project_operator_application_view_model(
        view_model_id="view-6",
        snapshot=snapshot(),
    )

    assert result.health_card.mode_label == "Mode: PAPER"
    assert result.health_card.broker_submission_label == (
        "Broker submission: DISABLED"
    )
    assert "No broker order submission" in result.read_only_notice


def test_projector_rejects_wrong_snapshot_type():
    with pytest.raises(TypeError, match="snapshot"):
        project_operator_application_view_model(
            view_model_id="view-7",
            snapshot=object(),
        )
