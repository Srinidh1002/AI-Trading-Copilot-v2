from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone

import pytest

from services.dashboard_read_models import (
    DashboardOpportunityViewV1,
    DashboardPaperFillViewV1,
    DashboardPaperPositionDetailViewV1,
    DashboardTradePlanTargetViewV1,
    DashboardTradePlanViewV1,
)


NOW = datetime(2026, 7, 30, 10, 0, tzinfo=timezone.utc)


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


def targets():
    return (
        DashboardTradePlanTargetViewV1(target_name="T1", target_price=120),
        DashboardTradePlanTargetViewV1(target_name="T2", target_price=140),
        DashboardTradePlanTargetViewV1(target_name="T3", target_price=160),
    )


def plan():
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
        targets=targets(),
    )


def fill():
    return DashboardPaperFillViewV1(
        fill_id="fill-1",
        fill_type="ENTRY",
        fill_reason="ENTRY_ACTIVATED",
        side="BUY",
        filled_lot_count=1,
        lot_size=75,
        filled_quantity=75,
        fill_price=100,
        gross_notional=7500,
        estimated_trading_cost=20,
        net_cash_effect=-7520,
        filled_at=NOW,
        source="PAPER",
    )


def test_opportunity_is_frozen_and_paper_only():
    value = opportunity()

    with pytest.raises(FrozenInstanceError):
        value.action = "SELL"

    with pytest.raises(ValueError, match="execution_mode must be PAPER"):
        DashboardOpportunityViewV1(
            **{
                **{
                    name: getattr(value, name)
                    for name in value.__dataclass_fields__
                },
                "execution_mode": "LIVE",
            }
        )


def test_plan_requires_ordered_three_targets_when_ready():
    value = plan()
    assert tuple(item.target_name for item in value.targets) == ("T1", "T2", "T3")

    with pytest.raises(ValueError, match="ordered exactly"):
        DashboardTradePlanViewV1(
            **{
                **{k: getattr(value, k) for k in value.__dataclass_fields__},
                "targets": (targets()[1], targets()[0], targets()[2]),
            }
        )


def test_blocked_plan_requires_blockers():
    value = plan()

    with pytest.raises(ValueError, match="requires blockers"):
        DashboardTradePlanViewV1(
            **{
                **{k: getattr(value, k) for k in value.__dataclass_fields__},
                "plan_status": "BLOCKED",
                "targets": (),
            }
        )


def test_fill_serialization_is_stable():
    value = fill()
    assert value.to_dict()["filled_at"] == NOW.isoformat()
    assert value.to_dict() == value.to_dict()


def test_position_detail_preserves_fill_order():
    second = DashboardPaperFillViewV1(
        fill_id="fill-2",
        fill_type="EXIT",
        fill_reason="TARGET_1",
        side="SELL",
        filled_lot_count=1,
        lot_size=75,
        filled_quantity=75,
        fill_price=120,
        gross_notional=9000,
        estimated_trading_cost=20,
        net_cash_effect=8980,
        filled_at=NOW,
        source="PAPER",
        target_name="T1",
    )

    value = DashboardPaperPositionDetailViewV1(
        paper_trade_id="trade-1",
        position_id="position-1",
        trade_plan_id="plan-1",
        integrated_trade_plan_result_id="integrated-1",
        lifecycle_state_id="lifecycle-1",
        lifecycle_state="CLOSED_TARGET_1",
        lifecycle_display_group="TERMINAL",
        transition_sequence=2,
        is_terminal=True,
        last_transition_code="TARGET_1",
        updated_at=NOW,
        fills=(fill(), second),
    )

    assert tuple(item.fill_id for item in value.fills) == ("fill-1", "fill-2")


def test_position_detail_rejects_non_tuple_fills():
    with pytest.raises(TypeError, match="exact tuple"):
        DashboardPaperPositionDetailViewV1(
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
            fills=[],
        )
