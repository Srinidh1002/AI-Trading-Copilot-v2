"""Task 6 Slice 6 Streamlit entry-point integration certification."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import dashboard.dashboard_v2 as dashboard_v2
from services.contracts.operator_application_view_model_v1 import (
    OperatorActiveTradeCardV1,
    OperatorApplicationViewModelV1,
    OperatorCapitalCardV1,
    OperatorHealthCardV1,
    OperatorMarketCardV1,
    OperatorRecommendationCardV1,
)


NOW = datetime(2026, 8, 3, 10, 45, tzinfo=timezone.utc)


def market_card(name, exchange):
    return OperatorMarketCardV1(
        title=name,
        exchange=exchange,
        score_label="Score: 0.75",
        confidence_label="Confidence: 80%",
        direction_label="Direction: BULLISH",
        eligibility_label="Eligibility: ELIGIBLE",
        freshness_label="Data: FRESH",
        reasons=("TREND_ALIGNED",),
        rejection_reasons=(),
    )


def view_model():
    return OperatorApplicationViewModelV1(
        view_model_id="view-1",
        generated_at=NOW,
        title="AI Trading Copilot",
        subtitle="NIFTY and SENSEX certified operator view",
        selected_market_banner="Selected market: NIFTY",
        losing_market_banner="Losing market: SENSEX | LOWER_SCORE",
        nifty_card=market_card("NIFTY", "NSE"),
        sensex_card=market_card("SENSEX", "BSE"),
        recommendation_card=OperatorRecommendationCardV1(
            action_label="Action: CALL",
            selected_market_label="Market: NIFTY",
            contract_label="Contract: NIFTY06AUG26C25000",
            entry_label="Entry: 100.00",
            stop_label="Stop: 90.00",
            targets_label="Targets: T1 110.00 | T2 120.00 | T3 130.00",
            confidence_label="Confidence: 82%",
            explanation=("NIFTY_OUTRANKED_SENSEX",),
        ),
        capital_card=OperatorCapitalCardV1(
            supplied_capital_label="Supplied capital: ₹100,000.00",
            usable_capital_label="Usable capital: ₹90,000.00",
            position_size_label="Position size: 2 lots / 50 quantity",
            capital_required_label="Capital required: ₹5,050.00",
            maximum_loss_label="Maximum loss: ₹1,000.00",
            daily_risk_used_label="Daily risk used: ₹1,000.00",
        ),
        active_trade_card=OperatorActiveTradeCardV1(
            status_label="Active trade: YES",
            contract_label="Contract: NIFTY06AUG26C25000",
            premium_label="Current premium: 105.00",
            pnl_label="Unrealized P&L: ₹250.00",
            target_status_label="Target status: T1_PENDING",
            stop_status_label="Stop status: ORIGINAL_STOP",
            instruction_label="Instruction: HOLD",
            confidence_warning_label="Confidence warning: STABLE",
        ),
        health_card=OperatorHealthCardV1(
            status_label="System status: HEALTHY",
            data_freshness_label="Data freshness: FRESH",
            data_connection_label="Data connection: CONNECTED",
            broker_connection_label="Broker connection: ISOLATED",
            mode_label="Mode: PAPER",
            broker_submission_label="Broker submission: DISABLED",
            emergency_halt_label="Emergency halt: CLEAR",
            runtime_label="Runtime: HEALTHY",
            journal_label="Journal: HEALTHY",
            warnings=(),
        ),
        read_only_notice="Read-only operator view. No broker order submission.",
    )


class FakeStreamlit:
    def __init__(self, session_state):
        self.session_state = session_state
        self.events = []

    def _record(self, name, *values):
        self.events.append((name, *values))

    def title(self, value):
        self._record("title", value)

    def caption(self, value):
        self._record("caption", value)

    def info(self, value):
        self._record("info", value)

    def subheader(self, value):
        self._record("subheader", value)

    def divider(self):
        self._record("divider")


def test_operator_view_model_takes_read_only_render_path(monkeypatch):
    fake_st = FakeStreamlit(
        {
            dashboard_v2._OPERATOR_VIEW_MODEL_KEY: view_model(),
        }
    )
    rendered = []

    monkeypatch.setattr(dashboard_v2, "st", fake_st)
    monkeypatch.setattr(
        dashboard_v2,
        "synchronize_registered_dashboard_publication",
        lambda state: None,
    )
    monkeypatch.setattr(
        dashboard_v2,
        "render_operator_dashboard",
        lambda *, st, view_model: rendered.append(
            (st, view_model)
        ),
    )
    monkeypatch.setattr(
        dashboard_v2,
        "get_plan_position_views",
        lambda state: pytest.fail("legacy path must not run"),
    )

    dashboard_v2.home()

    assert len(rendered) == 1
    assert rendered[0][0] is fake_st
    assert rendered[0][1].view_model_id == "view-1"


def test_missing_operator_view_preserves_existing_dashboard(monkeypatch):
    fake_st = FakeStreamlit({})
    plan_calls = []
    operational_calls = []

    monkeypatch.setattr(dashboard_v2, "st", fake_st)
    monkeypatch.setattr(
        dashboard_v2,
        "synchronize_registered_dashboard_publication",
        lambda state: None,
    )
    monkeypatch.setattr(
        dashboard_v2,
        "get_plan_position_views",
        lambda state: ("opportunity", "plan", "position"),
    )
    monkeypatch.setattr(
        dashboard_v2,
        "get_operational_views",
        lambda state: ("options", "runtime"),
    )
    monkeypatch.setattr(
        dashboard_v2,
        "render_plan_and_position_dashboard",
        lambda *args, **kwargs: plan_calls.append(
            (args, kwargs)
        ),
    )
    monkeypatch.setattr(
        dashboard_v2,
        "render_operational_dashboard",
        lambda *args, **kwargs: operational_calls.append(
            (args, kwargs)
        ),
    )

    dashboard_v2.home()

    assert len(plan_calls) == 1
    assert len(operational_calls) == 1
    assert ("title", "🤖 AI Trading Copilot V2") in fake_st.events


def test_invalid_operator_publication_fails_closed(monkeypatch):
    fake_st = FakeStreamlit(
        {
            dashboard_v2._OPERATOR_VIEW_MODEL_KEY: object(),
        }
    )

    monkeypatch.setattr(dashboard_v2, "st", fake_st)
    monkeypatch.setattr(
        dashboard_v2,
        "synchronize_registered_dashboard_publication",
        lambda state: None,
    )

    with pytest.raises(
        TypeError,
        match="operator_application_view_model_v1",
    ):
        dashboard_v2.home()


def test_operator_path_keeps_build_footer(monkeypatch):
    fake_st = FakeStreamlit(
        {
            dashboard_v2._OPERATOR_VIEW_MODEL_KEY: view_model(),
        }
    )

    monkeypatch.setattr(dashboard_v2, "st", fake_st)
    monkeypatch.setattr(
        dashboard_v2,
        "synchronize_registered_dashboard_publication",
        lambda state: None,
    )
    monkeypatch.setattr(
        dashboard_v2,
        "render_operator_dashboard",
        lambda **kwargs: None,
    )

    dashboard_v2.home()

    captions = [
        event[1]
        for event in fake_st.events
        if event[0] == "caption"
    ]
    assert any("Version" in caption for caption in captions)
