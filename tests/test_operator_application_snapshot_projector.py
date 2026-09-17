"""Task 6 Slice 2 operator snapshot projector certification."""
from datetime import datetime, timezone

import pytest

from services.contracts.operator_application_snapshot_v1 import (
    OperatorActiveTradeStateV1,
    OperatorCapitalStateV1,
    OperatorMarketStateV1,
    OperatorRecommendationStateV1,
    OperatorSystemHealthV1,
)
from services.operator.operator_application_snapshot_projector import (
    project_operator_application_snapshot,
)


NOW = datetime(2026, 8, 3, 10, 25, tzinfo=timezone.utc)


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


def project(**changes):
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
        recommendation=recommendation(),
        capital=capital(),
        active_trade=active_trade(),
        system_health=health(),
    )
    values.update(changes)
    return project_operator_application_snapshot(**values)


def inactive_trade():
    return active_trade(
        active=False,
        contract=None,
        current_premium=None,
        unrealized_pnl=0.0,
        target_status="NONE",
        stop_status="NONE",
        instruction="NONE",
    )


def wait_recommendation():
    return recommendation(
        action="WAIT",
        selected_market=None,
        contract=None,
        entry_price=None,
        stop_loss=None,
        target_1=None,
        target_2=None,
        target_3=None,
    )


def test_projects_nifty_winner_and_sensex_loser():
    result = project()

    assert result.selected_market == "NIFTY"
    assert result.losing_market == "SENSEX"
    assert result.losing_market_reasons == (
        "LOW_CONFIDENCE",
        "LOWER_SCORE",
        "LOWER_CONFIDENCE",
    )
    assert result.read_only is True


def test_projects_sensex_winner():
    result = project(
        nifty=market(
            "NIFTY",
            "NSE",
            score=0.4,
            confidence=0.5,
            eligible=False,
            rejection_reasons=("WEAK_STRUCTURE",),
        ),
        sensex=market(
            "SENSEX",
            "BSE",
            score=0.8,
            confidence=0.85,
        ),
        recommendation=recommendation(
            selected_market="SENSEX",
            contract="SENSEX07AUG26P80000",
            action="PUT",
        ),
        active_trade=active_trade(
            contract="SENSEX07AUG26P80000",
        ),
    )

    assert result.selected_market == "SENSEX"
    assert result.losing_market == "NIFTY"
    assert "WEAK_STRUCTURE" in result.losing_market_reasons


def test_wait_has_no_selected_or_losing_market():
    result = project(
        recommendation=wait_recommendation(),
        active_trade=inactive_trade(),
    )

    assert result.selected_market is None
    assert result.losing_market is None
    assert result.losing_market_reasons == ()


def test_ineligible_market_cannot_be_selected():
    with pytest.raises(ValueError, match="ineligible"):
        project(
            nifty=market(
                "NIFTY",
                "NSE",
                eligible=False,
            )
        )


def test_active_contract_must_match_recommendation():
    with pytest.raises(ValueError, match="contract mismatch"):
        project(
            active_trade=active_trade(
                contract="NIFTY06AUG26C25100",
            )
        )


def test_healthy_snapshot_cannot_contain_stale_market_data():
    with pytest.raises(ValueError, match="stale"):
        project(
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
        )


def test_degraded_snapshot_may_show_stale_data():
    result = project(
        sensex=market(
            "SENSEX",
            "BSE",
            score=0.35,
            confidence=0.5,
            eligible=False,
            direction="NEUTRAL",
            data_fresh=False,
            rejection_reasons=("STALE_DATA",),
        ),
        system_health=health(
            status="DEGRADED",
            data_fresh=False,
        ),
    )

    assert result.system_health.status == "DEGRADED"
    assert "STALE_DATA" in result.losing_market_reasons


def test_equal_certified_states_use_rank_reason():
    result = project(
        sensex=market(
            "SENSEX",
            "BSE",
            score=0.75,
            confidence=0.8,
            eligible=True,
        )
    )

    assert result.losing_market_reasons == (
        "LOWER_CERTIFIED_RANK",
    )


def test_projector_rejects_wrong_component_type():
    with pytest.raises(TypeError, match="nifty"):
        project(nifty=object())
