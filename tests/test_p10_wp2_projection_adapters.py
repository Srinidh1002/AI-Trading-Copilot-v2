from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from services.contracts.paper_trade_fill_v1 import PaperTradeFillV1
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)
from services.contracts.three_target_trade_plan_v1 import ThreeTargetTradePlanV1
from services.contracts.trade_opportunity_v1 import TradeOpportunityV1
from services.dashboard_read_models import (
    project_paper_trade_fill,
    project_paper_trade_position_detail,
    project_three_target_trade_plan,
    project_trade_opportunity,
)


NOW = datetime(2026, 7, 30, 10, 30, tzinfo=timezone.utc)


def exact(cls, **values):
    result = object.__new__(cls)
    for name, value in values.items():
        object.__setattr__(result, name, value)
    return result


def test_opportunity_projection_preserves_authoritative_values():
    source = exact(
        TradeOpportunityV1,
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
        strike=25000.0,
        expiry=date(2026, 8, 6),
        lot_size=75,
        reference_option_price=100.0,
        technical_strength=0.8,
        option_chain_strength=0.7,
        contract_ranking_score=0.9,
        decision_confidence=0.85,
        opportunity_score=0.82,
        supporting_evidence=("TECHNICAL",),
        contradictions=(),
        blockers=(),
        warnings=(),
       
    )

    result = project_trade_opportunity(source)

    assert result.opportunity_id == "opportunity-1"
    assert result.strike == 25000.0
    assert result.opportunity_score == 0.82


def test_ready_plan_projection_preserves_target_order():
    contract = SimpleNamespace(
        contract_id="contract-1",
        trading_symbol="NIFTY-CE",
        strike=25000.0,
        option_type="CALL",
    )
    target_1 = SimpleNamespace(
        target_number=1,
        target_price=120.0,
        reward_to_risk=1.0,
        allocation_fraction=0.5,
        warnings=(),
    )
    target_2 = SimpleNamespace(
        target_number=2,
        target_price=140.0,
        reward_to_risk=2.0,
        allocation_fraction=0.3,
        warnings=(),
    )
    target_3 = SimpleNamespace(
        target_number=3,
        target_price=160.0,
        reward_to_risk=3.0,
        allocation_fraction=0.2,
        warnings=(),
    )
    source = exact(
        ThreeTargetTradePlanV1,
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
        selected_option_contract=contract,
        target_1=target_1,
        target_2=target_2,
        target_3=target_3,
        entry_zone_lower=95.0,
        entry_zone_upper=105.0,
        entry_reference_price=100.0,
        entry_tolerance_fraction=0.05,
        maximum_chase_price=108.0,
        entry_method="LIMIT",
        stop_loss_price=90.0,
        stop_loss_method="STRUCTURE",
        stop_distance=10.0,
        stop_distance_fraction=0.1,
        lot_size=75,
        lot_count=1,
        quantity=75,
        available_capital=10000.0,
        required_capital=7500.0,
        risk_amount=750.0,
        maximum_permissible_loss=1000.0,
        estimated_entry_cost=10.0,
        estimated_exit_cost=10.0,
        estimated_total_charges=20.0,
        estimated_slippage_cost=5.0,
        expiry=date(2026, 8, 6),
        days_to_expiry=7,
        expiry_category="WEEKLY",
        invalidation_rules=("BREAK_STOP",),
        blockers=(),
        warnings=(),
        decision_reasons=("READY",),
        execution_mode="PAPER",
        live_execution_eligible=False,
    )

    result = project_three_target_trade_plan(source)

    assert tuple(item.target_name for item in result.targets) == (
        "T1",
        "T2",
        "T3",
    )
    assert tuple(item.booking_fraction for item in result.targets) == (
        0.5,
        0.3,
        0.2,
    )
    assert result.selected_option_symbol == "NIFTY-CE"


def test_fill_projection_preserves_cash_evidence():
    source = exact(
        PaperTradeFillV1,
        fill_id="fill-1",
        fill_type="ENTRY",
        fill_reason="ENTRY_ACTIVATED",
        side="BUY",
        filled_lot_count=1,
        lot_size=75,
        filled_quantity=75,
        fill_price=100.0,
        gross_notional=7500.0,
        estimated_trading_cost=20.0,
        net_cash_effect=-7520.0,
        filled_at=NOW,
        source="PAPER",
        target_name=None,
        warnings=(),
    )

    result = project_paper_trade_fill(source)

    assert result.fill_price == 100.0
    assert result.net_cash_effect == -7520.0


def test_pending_snapshot_projects_without_position():
    lifecycle = SimpleNamespace(
        lifecycle_state_id="lifecycle-1",
        trade_plan_id="plan-1",
        integrated_trade_plan_result_id="integrated-1",
        current_state="WAITING_FOR_ENTRY",
        transition_sequence=1,
        is_terminal=False,
        last_transition_code="WAITING_FOR_ENTRY",
        terminal_reason=None,
        terminal_target=None,
        blockers=(),
        warnings=(),
        decision_reasons=("WAIT",),
    )
    source = exact(
        PaperTradePersistenceSnapshotV1,
        paper_trade_id="trade-1",
        lifecycle_state=lifecycle,
        position=None,
        pnl_evidence=None,
        updated_at=NOW,
        execution_mode="PAPER",
        live_execution_eligible=False,
    )

    result = project_paper_trade_position_detail(source)

    assert result.lifecycle_display_group == "PENDING"
    assert result.position_id is None
    assert result.fills == ()


def test_latest_pnl_evidence_has_priority():
    entry_fill = exact(
        PaperTradeFillV1,
        fill_id="fill-entry",
        fill_type="ENTRY",
        fill_reason="ENTRY_ACTIVATED",
        side="BUY",
        filled_lot_count=1,
        lot_size=75,
        filled_quantity=75,
        fill_price=100.0,
        gross_notional=7500.0,
        estimated_trading_cost=20.0,
        net_cash_effect=-7520.0,
        filled_at=NOW,
        source="PAPER",
        target_name=None,
        warnings=(),
    )
    lifecycle = SimpleNamespace(
        lifecycle_state_id="lifecycle-1",
        trade_plan_id="plan-1",
        integrated_trade_plan_result_id="integrated-1",
        current_state="OPEN",
        transition_sequence=2,
        is_terminal=False,
        last_transition_code="ENTRY_ACTIVATED",
        terminal_reason=None,
        terminal_target=None,
        blockers=(),
        warnings=(),
        decision_reasons=(),
    )
    position = SimpleNamespace(
        position_id="position-1",
        market="NIFTY",
        exchange="NSE",
        underlying_symbol="NIFTY",
        option_symbol="NIFTY-CE",
        direction="BULLISH",
        option_type="CALL",
        strike=25000.0,
        expiry="2026-08-06",
        entry_fill=entry_fill,
        exit_fills=(),
        entry_price=100.0,
        opened_at=NOW,
        initial_lot_count=1,
        lot_size=75,
        initial_quantity=75,
        remaining_lot_count=1,
        remaining_quantity=75,
        target_1_lot_count=1,
        target_2_lot_count=0,
        target_3_lot_count=0,
        runner_lot_count=0,
        stop_loss=90.0,
        target_1=120.0,
        target_2=140.0,
        target_3=160.0,
        estimated_premium_outlay=7500.0,
        estimated_risk_amount=750.0,
        estimated_total_trading_cost=40.0,
        estimated_total_capital_requirement=7540.0,
        realized_net_pnl=10.0,
        unrealized_pnl=20.0,
        total_pnl=30.0,
        blockers=(),
        warnings=(),
        decision_reasons=(),
    )
    pnl = SimpleNamespace(
        realized_net_pnl_after=100.0,
        unrealized_pnl_after=200.0,
        total_pnl_after=300.0,
        current_option_price=104.0,
        calculated_at=NOW,
        warnings=("PERSISTED_PNL",),
    )
    source = exact(
        PaperTradePersistenceSnapshotV1,
        paper_trade_id="trade-1",
        lifecycle_state=lifecycle,
        position=position,
        pnl_evidence=pnl,
        updated_at=NOW,
        execution_mode="PAPER",
        live_execution_eligible=False,
    )

    result = project_paper_trade_position_detail(source)

    assert result.lifecycle_display_group == "ACTIVE"
    assert result.realized_net_pnl == 100.0
    assert result.unrealized_pnl == 200.0
    assert result.total_pnl == 300.0
    assert result.warnings == ("PERSISTED_PNL",)


@pytest.mark.parametrize(
    ("state", "group"),
    (
        ("PLANNED", "PENDING"),
        ("OPEN", "ACTIVE"),
        ("PARTIALLY_EXITED", "ACTIVE"),
        ("CLOSED_STOP", "TERMINAL"),
        ("BLOCKED", "BLOCKED"),
    ),
)
def test_lifecycle_display_group_is_fixed(state, group):
    lifecycle = SimpleNamespace(
        lifecycle_state_id="lifecycle-1",
        trade_plan_id="plan-1",
        integrated_trade_plan_result_id="integrated-1",
        current_state=state,
        transition_sequence=1,
        is_terminal=group in {"TERMINAL", "BLOCKED"},
        last_transition_code="TEST",
        terminal_reason=None,
        terminal_target=None,
        blockers=("BLOCKED",) if state == "BLOCKED" else (),
        warnings=(),
        decision_reasons=(),
    )
    source = exact(
        PaperTradePersistenceSnapshotV1,
        paper_trade_id="trade-1",
        lifecycle_state=lifecycle,
        position=None,
        pnl_evidence=None,
        updated_at=NOW,
        execution_mode="PAPER",
        live_execution_eligible=False,
    )

    assert project_paper_trade_position_detail(source).lifecycle_display_group == group


def test_projection_functions_reject_untyped_sources():
    with pytest.raises(TypeError):
        project_trade_opportunity(SimpleNamespace())
    with pytest.raises(TypeError):
        project_three_target_trade_plan(SimpleNamespace())
    with pytest.raises(TypeError):
        project_paper_trade_fill(SimpleNamespace())
    with pytest.raises(TypeError):
        project_paper_trade_position_detail(SimpleNamespace())
