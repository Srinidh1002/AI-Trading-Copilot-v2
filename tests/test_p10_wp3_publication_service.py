from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from services.contracts.paper_trade_fill_v1 import PaperTradeFillV1
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)
from services.contracts.three_target_trade_plan_v1 import (
    ThreeTargetTradePlanV1,
)
from services.contracts.trade_opportunity_v1 import TradeOpportunityV1
from services.dashboard_publication import (
    DashboardPublicationBuildInputV1,
    DashboardPublicationService,
)


NOW = datetime(2026, 7, 30, 12, 30, tzinfo=timezone.utc)


def exact(cls, **values):
    result = object.__new__(cls)
    for name, value in values.items():
        object.__setattr__(result, name, value)
    return result


def opportunity():
    return exact(
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


def plan():
    contract = SimpleNamespace(
        contract_id="contract-1",
        trading_symbol="NIFTY-CE",
        strike=25000.0,
        option_type="CALL",
    )
    targets = tuple(
        SimpleNamespace(
            target_number=number,
            target_price=100.0 + 20.0 * number,
            reward_to_risk=float(number),
            allocation_fraction=(0.5, 0.3, 0.2)[number - 1],
            warnings=(),
        )
        for number in (1, 2, 3)
    )
    return exact(
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
        target_1=targets[0],
        target_2=targets[1],
        target_3=targets[2],
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


def p7_snapshot():
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
    return exact(
        PaperTradePersistenceSnapshotV1,
        paper_trade_id="trade-1",
        lifecycle_state=lifecycle,
        position=None,
        pnl_evidence=None,
        updated_at=NOW,
        execution_mode="PAPER",
        live_execution_eligible=False,
    )


def build_input(**overrides):
    values = {
        "publication_id": "publication-1",
        "publication_sequence": 1,
        "published_at": NOW,
        "source_updated_at": NOW,
        "publication_status": "READY",
        "freshness_status": "FRESH",
        "trade_opportunity": opportunity(),
        "trade_plan": plan(),
        "p7_snapshot": p7_snapshot(),
    }
    values.update(overrides)
    return DashboardPublicationBuildInputV1(**values)


def test_service_projects_coherent_ready_publication():
    result = DashboardPublicationService().build(build_input())

    assert result.publication_id == "publication-1"
    assert result.opportunity.opportunity_id == "opportunity-1"
    assert result.trade_plan.trade_plan_id == "plan-1"
    assert result.paper_position.paper_trade_id == "trade-1"
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False


def test_service_preserves_ordered_targets():
    result = DashboardPublicationService().build(build_input())

    assert tuple(item.target_name for item in result.trade_plan.targets) == (
        "T1",
        "T2",
        "T3",
    )


def test_service_supports_blocked_no_view_publication():
    result = DashboardPublicationService().build(
        build_input(
            publication_status="BLOCKED",
            trade_opportunity=None,
            trade_plan=None,
            p7_snapshot=None,
            blockers=("SESSION_BLOCKED",),
        )
    )

    assert result.opportunity is None
    assert result.trade_plan is None
    assert result.paper_position is None
    assert result.blockers == ("SESSION_BLOCKED",)


def test_service_rejects_untyped_build_input():
    with pytest.raises(TypeError, match="exact DashboardPublicationBuildInputV1"):
        DashboardPublicationService().build(SimpleNamespace())


def test_build_input_rejects_untyped_sources():
    with pytest.raises(TypeError, match="trade_opportunity"):
        build_input(trade_opportunity=SimpleNamespace())


def test_build_input_rejects_future_source_timestamp():
    with pytest.raises(ValueError, match="cannot be later"):
        build_input(
            source_updated_at=datetime(
                2026,
                7,
                30,
                12,
                31,
                tzinfo=timezone.utc,
            )
        )


def test_envelope_rejects_plan_position_identity_mismatch():
    bad_lifecycle = SimpleNamespace(
        lifecycle_state_id="lifecycle-1",
        trade_plan_id="other-plan",
        integrated_trade_plan_result_id="integrated-1",
        current_state="WAITING_FOR_ENTRY",
        transition_sequence=1,
        is_terminal=False,
        last_transition_code="WAITING_FOR_ENTRY",
        terminal_reason=None,
        terminal_target=None,
        blockers=(),
        warnings=(),
        decision_reasons=(),
    )
    bad_snapshot = exact(
        PaperTradePersistenceSnapshotV1,
        paper_trade_id="trade-1",
        lifecycle_state=bad_lifecycle,
        position=None,
        pnl_evidence=None,
        updated_at=NOW,
        execution_mode="PAPER",
        live_execution_eligible=False,
    )

    with pytest.raises(ValueError, match="identity mismatch"):
        DashboardPublicationService().build(
            build_input(p7_snapshot=bad_snapshot)
        )
