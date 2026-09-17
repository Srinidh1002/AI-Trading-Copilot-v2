"""Task 6 Slice 3 operator snapshot runtime assembly certification."""
from datetime import datetime, timezone

import pytest

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
from services.operator.operator_snapshot_runtime import (
    run_operator_snapshot_runtime,
)


NOW = datetime(2026, 8, 3, 10, 30, tzinfo=timezone.utc)


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
        capital=capital(),
        active_trade=active_trade(),
        system_health=health(),
    )
    values.update(changes)
    return OperatorSnapshotRuntimeInputV1(**values)


def test_runtime_assembles_read_only_snapshot():
    result = run_operator_snapshot_runtime(
        snapshot_id="snapshot-1",
        runtime_input=runtime_input(),
    )

    assert result.snapshot_id == "snapshot-1"
    assert result.generated_at == NOW
    assert result.selected_market == "NIFTY"
    assert result.losing_market == "SENSEX"
    assert result.read_only is True


def test_runtime_preserves_all_certified_components():
    source = runtime_input()

    result = run_operator_snapshot_runtime(
        snapshot_id="snapshot-2",
        runtime_input=source,
    )

    assert result.nifty is source.nifty
    assert result.sensex is source.sensex
    assert result.recommendation is source.recommendation
    assert result.capital is source.capital
    assert result.active_trade is source.active_trade
    assert result.system_health is source.system_health


def test_wait_runtime_has_no_market_selection():
    result = run_operator_snapshot_runtime(
        snapshot_id="snapshot-wait",
        runtime_input=runtime_input(
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
            active_trade=active_trade(
                active=False,
                contract=None,
                current_premium=None,
                unrealized_pnl=0.0,
                target_status="NONE",
                stop_status="NONE",
                instruction="NONE",
            ),
        ),
    )

    assert result.selected_market is None
    assert result.losing_market is None


def test_runtime_input_requires_exact_component_types():
    with pytest.raises(TypeError, match="nifty"):
        runtime_input(nifty=object())


def test_runtime_rejects_wrong_input_type():
    with pytest.raises(TypeError, match="runtime_input"):
        run_operator_snapshot_runtime(
            snapshot_id="snapshot-1",
            runtime_input=object(),
        )


def test_runtime_fails_closed_on_unhealthy_stale_coherence():
    with pytest.raises(ValueError, match="stale"):
        run_operator_snapshot_runtime(
            snapshot_id="snapshot-1",
            runtime_input=runtime_input(
                sensex=market(
                    "SENSEX",
                    "BSE",
                    score=0.35,
                    confidence=0.5,
                    eligible=False,
                    direction="NEUTRAL",
                    data_fresh=False,
                    rejection_reasons=("STALE_DATA",),
                )
            ),
        )
