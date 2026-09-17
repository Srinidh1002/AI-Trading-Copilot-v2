from datetime import date, datetime, timezone

import pytest

from dashboard.dashboard_read_model_state import (
    OPPORTUNITY_STATE_KEY,
    PAPER_POSITION_STATE_KEY,
    TRADE_PLAN_STATE_KEY,
    get_plan_position_views,
)
from services.dashboard_read_models import (
    DashboardOpportunityViewV1,
    DashboardPaperPositionDetailViewV1,
    DashboardTradePlanTargetViewV1,
    DashboardTradePlanViewV1,
)


NOW = datetime(2026, 7, 30, 11, 30, tzinfo=timezone.utc)


def opportunity():
    return DashboardOpportunityViewV1(
        opportunity_id="opportunity-1",
        created_at=NOW,
        snapshot_id="snapshot-1",
        decision_id="decision-1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        opportunity_status="READY",
        action="BUY",
        directional_bias="BULLISH",
        option_type="CALL",
        contract_id="contract-1",
        trading_symbol="NIFTY-CE",
        instrument_token="token-1",
        strike=25000,
        expiry=date(2026, 8, 6),
        lot_size=75,
        reference_option_price=100,
        technical_strength=0.8,
        option_chain_strength=0.7,
        contract_ranking_score=0.9,
        decision_confidence=0.85,
        opportunity_score=0.82,
    )


def plan():
    targets = tuple(
        DashboardTradePlanTargetViewV1(
            target_name=f"T{number}",
            target_price=100 + number * 20,
        )
        for number in (1, 2, 3)
    )
    return DashboardTradePlanViewV1(
        trade_plan_id="plan-1",
        selected_opportunity_id="opportunity-1",
        evaluated_at=NOW,
        underlying_symbol="NIFTY",
        exchange="NSE",
        market="NIFTY",
        plan_status="READY",
        direction="BULLISH",
        instrument_type="INDEX_OPTION",
        opportunity_confidence=0.8,
        option_confidence=0.75,
        plan_confidence=0.78,
        targets=targets,
    )


def position():
    return DashboardPaperPositionDetailViewV1(
        paper_trade_id="trade-1",
        position_id=None,
        trade_plan_id="plan-1",
        integrated_trade_plan_result_id="integrated-1",
        lifecycle_state_id="lifecycle-1",
        lifecycle_state="WAITING_FOR_ENTRY",
        lifecycle_display_group="PENDING",
        transition_sequence=1,
        is_terminal=False,
        last_transition_code="WAITING_FOR_ENTRY",
        updated_at=NOW,
    )


def test_empty_state_returns_explicit_no_data_tuple():
    assert get_plan_position_views({}) == (None, None, None)


def test_state_boundary_returns_exact_views():
    expected = (opportunity(), plan(), position())
    state = {
        OPPORTUNITY_STATE_KEY: expected[0],
        TRADE_PLAN_STATE_KEY: expected[1],
        PAPER_POSITION_STATE_KEY: expected[2],
    }

    assert get_plan_position_views(state) == expected


@pytest.mark.parametrize(
    "key",
    (
        OPPORTUNITY_STATE_KEY,
        TRADE_PLAN_STATE_KEY,
        PAPER_POSITION_STATE_KEY,
    ),
)
def test_state_boundary_rejects_untyped_values(key):
    with pytest.raises(TypeError, match="must contain exact"):
        get_plan_position_views({key: {}})


def test_state_boundary_rejects_non_mapping():
    with pytest.raises(TypeError, match="state must be a mapping"):
        get_plan_position_views(object())
