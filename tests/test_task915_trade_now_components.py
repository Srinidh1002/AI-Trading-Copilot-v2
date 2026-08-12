from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

import dashboard.dashboard_v2 as dashboard_v2
from dashboard.trade_now_components import render_trade_now_dashboard
from dashboard.trades_pnl_components import filter_paper_trades, render_trades_pnl_center
from dashboard.manual_live_planner_components import build_manual_live_preview
from services.dashboard_read_models import (
    DashboardApplicationViewV1,
    DashboardMarketStateV1,
    DashboardOpportunityViewV1,
    DashboardPaperFillViewV1,
    DashboardPaperPositionDetailViewV1,
    DashboardPortfolioViewV1,
    DashboardTradePlanTargetViewV1,
    DashboardTradePlanViewV1,
)
from services.dashboard_read_models.task9_dashboard_shell import (
    build_task9_dashboard_shell_view,
)


NOW = datetime(2026, 8, 8, 10, 0, tzinfo=timezone.utc)


class FakeStreamlit:
    def __init__(self, events=None):
        self.events = [] if events is None else events

    def _record(self, name, *values):
        self.events.append((name, *values))

    def title(self, value): self._record("title", value)
    def caption(self, value): self._record("caption", value)
    def info(self, value): self._record("info", value)
    def warning(self, value): self._record("warning", value)
    def subheader(self, value): self._record("subheader", value)
    def write(self, value): self._record("write", value)
    def metric(self, label, value): self._record("metric", label, value)
    def columns(self, count):
        self._record("columns", count)
        return tuple(FakeStreamlit(self.events) for _ in range(count))


def market(name, freshness="FRESH"):
    return DashboardMarketStateV1(
        market=name, symbol=name, observed_at=NOW, market_status="OPEN",
        data_status="PUBLISHED", freshness_status=freshness,
    )


def opportunity(action="CALL", status="READY"):
    return DashboardOpportunityViewV1(
        opportunity_id="opp-1", created_at=NOW, snapshot_id="snapshot-1",
        decision_id="decision-1", underlying_symbol="NIFTY", exchange="NSE",
        opportunity_status=status, action=action, directional_bias="BULLISH",
        option_type=action if action in {"CALL", "PUT"} else None,
        contract_id="contract-1", trading_symbol="NIFTY-CE", instrument_token="token-1",
        strike=25000, expiry=None, lot_size=75, reference_option_price=100,
        technical_strength=.8, option_chain_strength=.7, contract_ranking_score=.9,
        decision_confidence=.82, opportunity_score=.85,
    )


def plan():
    return DashboardTradePlanViewV1(
        trade_plan_id="plan-1", selected_opportunity_id="opp-1", evaluated_at=NOW,
        underlying_symbol="NIFTY", exchange="NSE", market="NIFTY", plan_status="READY",
        direction="BULLISH", instrument_type="INDEX_OPTION", opportunity_confidence=.82,
        option_confidence=.8, plan_confidence=.84, selected_option_symbol="NIFTY-CE",
        strike=25000, entry_zone_lower=98, entry_zone_upper=102,
        entry_reference_price=100, maximum_chase_price=104, stop_loss_price=92,
        targets=tuple(DashboardTradePlanTargetViewV1(f"T{i}", 100 + i * 10) for i in (1, 2, 3)),
        lot_size=75, lot_count=1, quantity=75, required_capital=7500,
        risk_amount=600, estimated_total_charges=25,
        invalidation_rules=("Stop loss reached.",), decision_reasons=("Trend aligned.",),
    )


def view(**changes):
    values = dict(
        view_id="view-1", generated_at=NOW, market_session_state="OPEN",
        nifty_market=market("NIFTY"), sensex_market=market("SENSEX"),
        selected_market="NIFTY", selected_market_rationale=("NIFTY ranked higher.",),
        rejected_market_rationale=("SENSEX confidence was lower.",),
        primary_opportunity=opportunity(), primary_trade_plan=plan(),
    )
    values.update(changes)
    return DashboardApplicationViewV1(**values)


def position(**changes):
    fill = DashboardPaperFillViewV1(
        fill_id="fill-1", fill_type="ENTRY", fill_reason="SIMULATED_ENTRY",
        side="BUY", filled_lot_count=1, lot_size=75, filled_quantity=75,
        fill_price=100, gross_notional=7500, estimated_trading_cost=25,
        net_cash_effect=-7525, filled_at=NOW, source="PAPER",
    )
    values = dict(
        paper_trade_id="paper-1", position_id="position-1", trade_plan_id="plan-1",
        integrated_trade_plan_result_id="integrated-1", lifecycle_state_id="state-1",
        lifecycle_state="OPEN", lifecycle_display_group="ACTIVE", transition_sequence=4,
        is_terminal=False, last_transition_code="ENTRY_CONFIRMED", updated_at=NOW,
        market="NIFTY", option_symbol="NIFTY-CE", entry_price=100,
        current_option_price=106, remaining_quantity=75, stop_loss=92,
        target_1=110, target_2=120, target_3=130, realized_net_pnl=10,
        unrealized_pnl=450, total_pnl=460, estimated_total_capital_requirement=7500,
        fills=(fill,),
    )
    values.update(changes)
    return DashboardPaperPositionDetailViewV1(**values)


def written(st, event):
    return [item[1:] for item in st.events if item[0] == event]


def test_ready_plan_renders_paper_safety_selected_market_and_geometry():
    st = FakeStreamlit()
    source = view()

    render_trade_now_dashboard(st=st, view=source)

    assert ("PAPER ONLY · NO REAL ORDER WILL BE SENT · BROKER ORDER SUBMISSION DISABLED",) in written(st, "info")
    assert ("Selected Market", "NIFTY") in written(st, "metric")
    assert ("Contract: NIFTY-CE",) in written(st, "write")
    assert ("Entry lower: 98.0",) in written(st, "write")
    assert ("Stop loss: 92.0",) in written(st, "write")
    assert ("T1: 110.0",) in written(st, "write")
    assert ("T2: 120.0",) in written(st, "write")
    assert ("T3: 130.0",) in written(st, "write")
    assert ("- SENSEX confidence was lower.",) in written(st, "write")
    assert source.primary_trade_plan.plan_status == "READY"


def test_trade_now_has_page_heading_not_a_second_application_title():
    st = FakeStreamlit()

    render_trade_now_dashboard(st=st, view=view())

    assert ("Trade Now",) in written(st, "subheader")
    assert ("AI TRADING COPILOT",) not in written(st, "title")


def test_prepublication_shell_hides_internal_timestamp_but_published_view_keeps_it():
    shell = FakeStreamlit()
    published = FakeStreamlit()

    render_trade_now_dashboard(
        st=shell,
        view=build_task9_dashboard_shell_view(),
    )
    render_trade_now_dashboard(st=published, view=view())

    assert ("Evaluated/generated: Not yet published",) in written(shell, "caption")
    assert not any("1970-01-01" in item[0] for item in written(shell, "caption"))
    assert (f"Evaluated/generated: {NOW.isoformat()}",) in written(published, "caption")


@pytest.mark.parametrize("market_name", ["NIFTY", "SENSEX"])
def test_selected_market_and_cards_remain_distinct(market_name):
    st = FakeStreamlit()
    source = (
        view(selected_market=market_name)
        if market_name == "NIFTY"
        else view(
            selected_market=market_name,
            primary_opportunity=None,
            primary_trade_plan=None,
        )
    )

    render_trade_now_dashboard(st=st, view=source)

    assert ("Selected Market", market_name) in written(st, "metric")
    assert ("NIFTY",) in written(st, "subheader")
    assert ("SENSEX",) in written(st, "subheader")


@pytest.mark.parametrize("action", ["WAIT", "NO_TRADE"])
def test_wait_and_no_trade_are_not_rendered_as_trade_ready(action):
    st = FakeStreamlit()
    source = view(primary_opportunity=opportunity(action, action), primary_trade_plan=None)

    render_trade_now_dashboard(st=st, view=source)

    assert ("Status", action) in written(st, "metric")
    assert ("Status", "TRADE READY") not in written(st, "metric")


def test_closed_stale_and_blocked_views_are_visibly_non_actionable():
    for source, status in (
        (view(market_session_state="MARKET_CLOSED"), "MARKET CLOSED"),
        (view(nifty_market=market("NIFTY", "STALE")), "STALE"),
        (view(blockers=("Provider unavailable.",)), "BLOCKED"),
    ):
        st = FakeStreamlit()
        render_trade_now_dashboard(st=st, view=source)
        assert ("Status", status) in written(st, "metric")
        assert written(st, "warning")


@pytest.mark.parametrize(
    "changes",
    (
        {"selected_market": None},
        {"nifty_market": None},
        {"primary_opportunity": opportunity("WAIT", "WAIT")},
        {"primary_opportunity": opportunity("NO_TRADE", "NO_TRADE")},
    ),
)
def test_incoherent_ready_evidence_never_renders_trade_ready(changes):
    st = FakeStreamlit()
    source = view(**changes)

    render_trade_now_dashboard(st=st, view=source)

    assert ("Status", "TRADE READY") not in written(st, "metric")
    assert ("Status", "DATA UNAVAILABLE") in written(st, "metric")


def test_missing_optional_values_are_safe_and_renderer_has_no_execution_controls():
    st = FakeStreamlit()
    source = DashboardApplicationViewV1(
        view_id="empty", generated_at=NOW, market_session_state="CLOSED",
    )

    render_trade_now_dashboard(st=st, view=source)

    assert ("Status", "MARKET CLOSED") in written(st, "metric")
    assert {"button", "form_submit_button", "checkbox", "toggle"}.isdisjoint(item[0] for item in st.events)
    assert source.broker_order_submission is False
    assert source.live_execution_eligible is False


def test_active_position_dominates_and_renders_authoritative_details_without_mutation():
    st = FakeStreamlit()
    active = position()
    source = view(active_paper_position=active)

    render_trade_now_dashboard(st=st, view=source)

    assert ("ACTIVE PAPER POSITION",) in written(st, "subheader")
    assert ("Contract", "NIFTY-CE") in written(st, "metric")
    assert ("Entry", "100.0") in written(st, "metric")
    assert ("Current Premium", "106.0") in written(st, "metric")
    assert ("Remaining Quantity", "75") in written(st, "metric")
    assert ("Realized P&L", "10.0") in written(st, "metric")
    assert ("T3", "130.0") in written(st, "metric")
    assert any("SIMULATED_ENTRY" in item[0] for item in written(st, "write"))
    assert source.active_paper_position is active


def test_terminal_or_reference_only_active_position_remains_visible():
    terminal = position(
        is_terminal=True, lifecycle_state="CLOSED", lifecycle_display_group="TERMINAL",
        terminal_reason="STOP_HIT", terminal_target="STOP",
    )
    for source in (
        view(active_paper_position=terminal),
        view(active_paper_position=position(), market_session_state="MARKET_CLOSED"),
        view(active_paper_position=position(), blockers=("Stale lifecycle.",)),
    ):
        st = FakeStreamlit()
        render_trade_now_dashboard(st=st, view=source)
        assert ("ACTIVE PAPER POSITION",) in written(st, "subheader") or ("POSITION CLOSED",) in written(st, "subheader")
        assert written(st, "warning")
    st = FakeStreamlit()
    render_trade_now_dashboard(st=st, view=view(active_paper_position=terminal))
    assert ("Terminal reason: STOP_HIT",) in written(st, "write")


def test_trades_pnl_center_uses_published_portfolio_history_and_fills():
    st = FakeStreamlit()
    open_trade = position()
    closed_trade = position(
        paper_trade_id="paper-2", is_terminal=True, lifecycle_state="CLOSED",
        lifecycle_display_group="TERMINAL", terminal_reason="TARGET_HIT",
    )
    portfolio = DashboardPortfolioViewV1(
        portfolio_id="portfolio", trading_day_id="2026-08-08", updated_at=NOW,
        starting_capital=100000, available_cash=90000, reserved_capital=0,
        deployed_capital=7500, committed_capital=7500, realized_net_pnl=10,
        unrealized_pnl=450, total_pnl=460, total_equity=100460,
        open_position_count=1, pending_plan_count=0, concurrent_trade_count=1,
        aggregate_committed_risk=600, event_sequence=1,
    )
    source = view(active_paper_position=open_trade, paper_trade_history=(closed_trade,), portfolio=portfolio)

    render_trades_pnl_center(st=st, view=source)

    values = [item[0] for item in written(st, "write")]
    assert any("Starting capital: 100000.0" in value for value in values)
    assert any("Total equity: 100460.0" in value for value in values)
    assert any("paper-1" in value for value in values)
    assert any("paper-2" in value for value in values)
    assert any("SIMULATED_ENTRY" in value for value in values)
    assert filter_paper_trades((open_trade, closed_trade), status="OPEN") == (open_trade,)
    assert filter_paper_trades((open_trade, closed_trade), status="CLOSED") == (closed_trade,)


def test_trades_pnl_center_has_safe_empty_state():
    st = FakeStreamlit()
    render_trades_pnl_center(st=st, view=DashboardApplicationViewV1(view_id="empty", generated_at=NOW, market_session_state="CLOSED"))
    assert ("No published PAPER portfolio summary is available.",) in written(st, "info")
    assert ("No published PAPER trades are available.",) in written(st, "info")


def test_manual_preview_risk_budget_scales_only_published_risk_geometry():
    published = plan()
    source = view(primary_trade_plan=published)
    capital_only = build_manual_live_preview(view=source, capital=30000)
    risk_limited = build_manual_live_preview(view=source, capital=30000, risk_budget=600)
    assert capital_only.recommended_lot_count == 4
    assert risk_limited.recommended_lot_count == 1
    assert risk_limited.estimated_max_loss == 600
    assert risk_limited.published_plan_maximum_permissible_loss is None
    assert risk_limited.risk_basis == "SCALED_PUBLISHED_PER_LOT_RISK"
    insufficient = build_manual_live_preview(view=source, capital=30000, risk_budget=599)
    assert insufficient.recommended_lot_count == 0
    assert insufficient.status == "INSUFFICIENT_RISK_BUDGET"


def test_component_has_no_provider_or_execution_imports():
    source = (Path(__file__).resolve().parents[1] / "dashboard" / "trade_now_components.py").read_text(encoding="utf-8")
    for forbidden in ("angel_", "Angel", "submit_order", "execute_trade", "streamlit"):
        assert forbidden not in source


def test_dashboard_renders_unified_trade_now_before_operator_view(monkeypatch):
    class HomeStreamlit(FakeStreamlit):
        def __init__(self, session_state):
            super().__init__()
            self.session_state = session_state

        def divider(self): self._record("divider")

    source = view()
    fake_st = HomeStreamlit({"dashboard_application_view_v1": source})
    rendered = []
    monkeypatch.setattr(dashboard_v2, "st", fake_st)
    monkeypatch.setattr(dashboard_v2, "synchronize_registered_dashboard_publication", lambda state: False)
    monkeypatch.setattr(dashboard_v2, "get_operator_application_view_model", lambda state: "operator-view")
    monkeypatch.setattr(dashboard_v2, "render_trade_now_dashboard", lambda *, st, view: rendered.append(("trade_now", view)))
    monkeypatch.setattr(dashboard_v2, "render_operator_dashboard", lambda **kwargs: rendered.append(("operator", kwargs["view_model"])))
    monkeypatch.setattr(dashboard_v2, "get_plan_position_views", lambda state: ("opportunity", "plan", "position"))
    monkeypatch.setattr(dashboard_v2, "get_operational_views", lambda state: ("options", "runtime"))
    monkeypatch.setattr(dashboard_v2, "get_r4_paper_lifecycle_view", lambda state: "lifecycle")
    monkeypatch.setattr(dashboard_v2, "render_plan_and_position_dashboard", lambda *args, **kwargs: rendered.append(("plan_position", kwargs)))
    monkeypatch.setattr(dashboard_v2, "_render_r4_lifecycle_section", lambda value: rendered.append(("lifecycle", value)))
    monkeypatch.setattr(dashboard_v2, "render_operational_dashboard", lambda *args, **kwargs: rendered.append(("operational", kwargs)))

    dashboard_v2.home()

    assert [item[0] for item in rendered] == ["trade_now", "operator"]
    assert rendered.count(("operator", "operator-view")) == 1
