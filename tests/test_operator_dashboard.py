"""Task 6 Slice 5 Streamlit operator dashboard renderer certification."""
from datetime import datetime, timezone

import pytest

from dashboard.operator_dashboard import render_operator_dashboard
from services.contracts.operator_application_view_model_v1 import (
    OperatorActiveTradeCardV1,
    OperatorApplicationViewModelV1,
    OperatorCapitalCardV1,
    OperatorHealthCardV1,
    OperatorMarketCardV1,
    OperatorRecommendationCardV1,
)


NOW = datetime(2026, 8, 3, 10, 40, tzinfo=timezone.utc)


class FakeStreamlit:
    def __init__(self, events=None):
        self.events = [] if events is None else events

    def _record(self, name, *values):
        self.events.append((name, *values))

    def title(self, value):
        self._record("title", value)

    def caption(self, value):
        self._record("caption", value)

    def info(self, value):
        self._record("info", value)

    def success(self, value):
        self._record("success", value)

    def warning(self, value):
        self._record("warning", value)

    def subheader(self, value):
        self._record("subheader", value)

    def write(self, value):
        self._record("write", value)

    def metric(self, label, value):
        self._record("metric", label, value)

    def columns(self, count):
        self._record("columns", count)
        return tuple(FakeStreamlit(self.events) for _ in range(count))


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


def view_model(**changes):
    values = dict(
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
    values.update(changes)
    return OperatorApplicationViewModelV1(**values)


def event_values(events, name):
    return [event[1:] for event in events if event[0] == name]


def test_renderer_displays_core_operator_sections():
    st = FakeStreamlit()
    render_operator_dashboard(st=st, view_model=view_model())

    assert ("AI Trading Copilot",) in event_values(st.events, "title")
    headings = event_values(st.events, "subheader")
    assert ("Market Comparison",) in headings
    assert ("Recommendation",) in headings
    assert ("Capital and Risk",) in headings
    assert ("Active Trade",) in headings
    assert ("System Health",) in headings


def test_renderer_keeps_paper_safety_visible():
    st = FakeStreamlit()
    render_operator_dashboard(st=st, view_model=view_model())

    written = event_values(st.events, "write")
    info = event_values(st.events, "info")
    assert ("Mode: PAPER",) in written
    assert ("Broker submission: DISABLED",) in written
    assert ("Read-only operator view. No broker order submission.",) in info


def test_renderer_displays_market_comparison():
    st = FakeStreamlit()
    render_operator_dashboard(st=st, view_model=view_model())

    headings = event_values(st.events, "subheader")
    assert ("NIFTY · NSE",) in headings
    assert ("SENSEX · BSE",) in headings
    assert ("Losing market: SENSEX | LOWER_SCORE",) in event_values(
        st.events,
        "warning",
    )


def test_renderer_displays_recommendation_geometry():
    st = FakeStreamlit()
    render_operator_dashboard(st=st, view_model=view_model())

    written = event_values(st.events, "write")
    assert ("Entry: 100.00",) in written
    assert ("Stop: 90.00",) in written
    assert ("Targets: T1 110.00 | T2 120.00 | T3 130.00",) in written


def test_renderer_warns_on_deteriorating_confidence():
    st = FakeStreamlit()
    source = view_model()
    deteriorating = OperatorActiveTradeCardV1(
        status_label=source.active_trade_card.status_label,
        contract_label=source.active_trade_card.contract_label,
        premium_label=source.active_trade_card.premium_label,
        pnl_label=source.active_trade_card.pnl_label,
        target_status_label=source.active_trade_card.target_status_label,
        stop_status_label=source.active_trade_card.stop_status_label,
        instruction_label=source.active_trade_card.instruction_label,
        confidence_warning_label="Confidence warning: DETERIORATING",
    )

    render_operator_dashboard(
        st=st,
        view_model=view_model(active_trade_card=deteriorating),
    )

    assert ("Confidence warning: DETERIORATING",) in event_values(
        st.events,
        "warning",
    )


def test_renderer_has_no_trade_or_broker_action_controls():
    st = FakeStreamlit()
    render_operator_dashboard(st=st, view_model=view_model())

    prohibited = {"button", "form_submit_button", "checkbox", "toggle"}
    assert prohibited.isdisjoint(event[0] for event in st.events)


def test_renderer_rejects_wrong_view_model_type():
    with pytest.raises(TypeError, match="view_model"):
        render_operator_dashboard(st=FakeStreamlit(), view_model=object())
