from datetime import date, datetime, timezone

from dashboard.plan_position_components import (
    render_plan_and_position_dashboard,
)
from services.dashboard_read_models import (
    DashboardOpportunityViewV1,
    DashboardPaperPositionDetailViewV1,
    DashboardTradePlanTargetViewV1,
    DashboardTradePlanViewV1,
)


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)


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


def test_complete_no_data_render_is_explicit():
    st = FakeStreamlit()

    render_plan_and_position_dashboard(
        st,
        opportunity=None,
        plan=None,
        position=None,
    )

    assert (
        "info",
        "No certified P6 opportunity is available.",
    ) in st.calls
    assert (
        "info",
        "No certified P6 trade plan is available.",
    ) in st.calls
    assert (
        "info",
        "No certified P7 paper position is available.",
    ) in st.calls


def test_blocked_plan_never_renders_targets():
    st = FakeStreamlit()
    plan = DashboardTradePlanViewV1(
        trade_plan_id="plan-1",
        selected_opportunity_id="opportunity-1",
        evaluated_at=NOW,
        underlying_symbol="NIFTY",
        exchange="NSE",
        market="NIFTY",
        plan_status="BLOCKED",
        direction="BULLISH",
        instrument_type="INDEX_OPTION",
        opportunity_confidence=0.8,
        option_confidence=None,
        plan_confidence=0.5,
        targets=(),
        blockers=("RISK_BLOCKED",),
    )

    render_plan_and_position_dashboard(
        st,
        opportunity=None,
        plan=plan,
        position=None,
    )

    metrics = tuple(call for call in st.calls if call[0] == "metric")
    assert not any(call[1] in {"T1", "T2", "T3"} for call in metrics)
    assert ("error", "RISK_BLOCKED") in st.calls


def test_ready_plan_renders_ordered_targets():
    st = FakeStreamlit()
    opportunity = DashboardOpportunityViewV1(
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
    targets = tuple(
        DashboardTradePlanTargetViewV1(
            target_name=f"T{number}",
            target_price=100 + number * 20,
        )
        for number in (1, 2, 3)
    )
    plan = DashboardTradePlanViewV1(
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
    position = DashboardPaperPositionDetailViewV1(
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

    render_plan_and_position_dashboard(
        st,
        opportunity=opportunity,
        plan=plan,
        position=position,
    )

    target_metrics = tuple(
        call[1]
        for call in st.calls
        if call[0] == "metric" and call[1] in {"T1", "T2", "T3"}
    )
    assert target_metrics == ("T1", "T2", "T3")
