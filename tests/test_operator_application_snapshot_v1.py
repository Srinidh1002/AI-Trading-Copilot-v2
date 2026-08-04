"""Task 6 Slice 1 read-only operator snapshot contract certification."""
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


NOW = datetime(2026, 8, 3, 10, 20, tzinfo=timezone.utc)


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


def capital(**changes):
    values = dict(
        supplied_capital=100000.0,
        usable_capital=90000.0,
        lots=2,
        quantity=50,
        capital_required=5050.0,
        maximum_loss=1000.0,
        daily_risk_used=1000.0,
    )
    values.update(changes)
    return OperatorCapitalStateV1(**values)


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
        losing_market_reasons=("LOWER_RISK_ADJUSTED_SCORE",),
        recommendation=recommendation(),
        capital=capital(),
        active_trade=active_trade(),
        system_health=health(),
    )
    values.update(changes)
    return OperatorApplicationSnapshotV1(**values)


def test_complete_read_only_snapshot_is_valid():
    result = snapshot()

    assert result.read_only is True
    assert result.selected_market == "NIFTY"
    assert result.recommendation.action == "CALL"
    assert result.system_health.broker_submission_enabled is False


def test_wait_recommendation_has_no_trade_geometry():
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
    result = snapshot(
        selected_market=None,
        losing_market=None,
        recommendation=wait,
    )

    assert result.recommendation.action == "WAIT"


def test_executable_recommendation_requires_full_geometry():
    with pytest.raises(ValueError, match="geometry"):
        recommendation(contract=None)


def test_non_executable_recommendation_rejects_geometry():
    with pytest.raises(ValueError, match="non-executable"):
        recommendation(action="NO_TRADE")


def test_inactive_trade_is_strict():
    result = active_trade(
        active=False,
        contract=None,
        current_premium=None,
        unrealized_pnl=0.0,
        target_status="NONE",
        stop_status="NONE",
        instruction="NONE",
    )
    assert result.active is False

    with pytest.raises(ValueError, match="inactive"):
        active_trade(active=False)


def test_paper_mode_cannot_enable_broker_submission():
    with pytest.raises(ValueError, match="disabled"):
        health(broker_submission_enabled=True)


def test_snapshot_is_always_read_only():
    with pytest.raises(ValueError, match="read-only"):
        snapshot(read_only=False)


def test_selected_market_must_match_recommendation():
    with pytest.raises(ValueError, match="mismatch"):
        snapshot(
            selected_market="SENSEX",
            losing_market="NIFTY",
        )


def test_market_identity_is_strict():
    with pytest.raises(ValueError, match="identity"):
        market("NIFTY", "BSE")


def test_capital_cannot_be_overspent():
    with pytest.raises(ValueError, match="capital_required"):
        capital(capital_required=95000.0)
