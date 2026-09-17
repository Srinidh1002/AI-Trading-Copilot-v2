from datetime import date, datetime, timezone

import pytest

from dashboard.plan_position_components import (
    render_opportunity_card,
    render_paper_position_card,
    render_plan_and_position_dashboard,
    render_trade_plan_card,
)
from services.dashboard_read_models import (
    DashboardOpportunityViewV1,
    DashboardPaperFillViewV1,
    DashboardPaperPositionDetailViewV1,
    DashboardTradePlanTargetViewV1,
    DashboardTradePlanViewV1,
)


NOW = datetime(2026, 7, 30, 11, 0, tzinfo=timezone.utc)


class Element:
    def __init__(self, root):
        self.root = root

    def metric(self, label, value, *args, **kwargs):
        self.root.calls.append(("metric", label, value))

    def caption(self, value, *args, **kwargs):
        self.root.calls.append(("caption", value))

    def warning(self, value, *args, **kwargs):
        self.root.calls.append(("warning", value))


class FakeStreamlit:
    def __init__(self):
        self.calls = []

    def columns(self, count):
        self.calls.append(("columns", count))
        return tuple(Element(self) for _ in range(count))

    def __getattr__(self, name):
        def method(*args, **kwargs):
            self.calls.append((name, *args))
        return method


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
        DashboardTradePlanTargetViewV1(
            target_name="T1",
            target_price=120,
            reward_to_risk=1,
            booking_fraction=0.5,
        ),
        DashboardTradePlanTargetViewV1(
            target_name="T2",
            target_price=140,
            reward_to_risk=2,
            booking_fraction=0.3,
        ),
        DashboardTradePlanTargetViewV1(
            target_name="T3",
            target_price=160,
            reward_to_risk=3,
            booking_fraction=0.2,
        ),
    )


def plan(status="READY"):
    return DashboardTradePlanViewV1(
        trade_plan_id="plan-1",
        selected_opportunity_id="opportunity-1",
        evaluated_at=NOW,
        underlying_symbol="NIFTY",
        exchange="NSE",
        market="NIFTY",
        plan_status=status,
        direction="BULLISH",
        instrument_type="INDEX_OPTION",
        opportunity_confidence=0.8,
        option_confidence=0.75,
        plan_confidence=0.78,
        selected_option_symbol="NIFTY-CE",
        strike=25000,
        entry_zone_lower=95,
        entry_zone_upper=105,
        entry_reference_price=100,
        maximum_chase_price=108,
        stop_loss_price=90,
        targets=targets() if status == "READY" else (),
        quantity=75,
        risk_amount=750,
        required_capital=7500,
        estimated_total_charges=20,
        expiry=date(2026, 8, 6),
        blockers=("PLAN_BLOCKED",) if status == "BLOCKED" else (),
        decision_reasons=("NO_TRADE",) if status == "NO_TRADE" else (),
    )


def position():
    fill = DashboardPaperFillViewV1(
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
    return DashboardPaperPositionDetailViewV1(
        paper_trade_id="trade-1",
        position_id="position-1",
        trade_plan_id="plan-1",
        integrated_trade_plan_result_id="integrated-1",
        lifecycle_state_id="lifecycle-1",
        lifecycle_state="OPEN",
        lifecycle_display_group="ACTIVE",
        transition_sequence=2,
        is_terminal=False,
        last_transition_code="ENTRY_ACTIVATED",
        updated_at=NOW,
        option_symbol="NIFTY-CE",
        entry_price=100,
        remaining_quantity=75,
        stop_loss=90,
        target_1=120,
        target_2=140,
        target_3=160,
        realized_net_pnl=0,
        unrealized_pnl=300,
        total_pnl=300,
        current_option_price=104,
        estimated_total_capital_requirement=7540,
        fills=(fill,),
    )


def calls_named(st, name):
    return tuple(call for call in st.calls if call[0] == name)


def test_opportunity_none_renders_explicit_no_data():
    st = FakeStreamlit()
    render_opportunity_card(st, None)
    assert ("info", "No certified P6 opportunity is available.") in st.calls


def test_opportunity_card_uses_read_model_values():
    st = FakeStreamlit()
    render_opportunity_card(st, opportunity())
    metrics = calls_named(st, "metric")
    assert ("metric", "Action", "BUY") in metrics
    assert ("metric", "Strike", 25000.0) in metrics


def test_ready_plan_renders_three_targets():
    st = FakeStreamlit()
    render_trade_plan_card(st, plan())
    metrics = calls_named(st, "metric")
    assert ("metric", "T1", "₹120.00") in metrics
    assert ("metric", "T2", "₹140.00") in metrics
    assert ("metric", "T3", "₹160.00") in metrics


def test_blocked_plan_does_not_render_target_metrics():
    st = FakeStreamlit()
    render_trade_plan_card(st, plan("BLOCKED"))
    metrics = calls_named(st, "metric")
    assert not any(item[1] in {"T1", "T2", "T3"} for item in metrics)
    assert ("error", "PLAN_BLOCKED") in st.calls


def test_position_uses_persisted_pnl_and_fill_rows():
    st = FakeStreamlit()
    render_paper_position_card(st, position())
    metrics = calls_named(st, "metric")
    assert ("metric", "Total P&L", "₹300.00") in metrics
    dataframes = calls_named(st, "dataframe")
    assert len(dataframes) == 1
    rows = dataframes[0][1]
    assert rows[0]["Reason"] == "ENTRY_ACTIVATED"


def test_combined_renderer_orders_sections():
    st = FakeStreamlit()
    render_plan_and_position_dashboard(
        st,
        opportunity=opportunity(),
        plan=plan(),
        position=position(),
    )
    names = tuple(item[0] for item in st.calls)
    assert names[0] == "header"
    assert names.count("divider") == 2


@pytest.mark.parametrize(
    ("function", "value"),
    (
        (render_opportunity_card, object()),
        (render_trade_plan_card, object()),
        (render_paper_position_card, object()),
    ),
)
def test_components_reject_untyped_values(function, value):
    with pytest.raises(TypeError):
        function(FakeStreamlit(), value)
