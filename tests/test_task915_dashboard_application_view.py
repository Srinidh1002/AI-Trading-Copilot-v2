from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dashboard.dashboard_publication_sync import (
    APPLICATION_VIEW_STATE_KEY,
    synchronize_dashboard_publication,
)
from dashboard.dashboard_status_components import (
    DashboardPublicationStatusViewV1,
    render_dashboard_status,
)
from dashboard.task9_certification_components import (
    render_task9_certification_center,
)
from dashboard.recommendation_history_components import (
    filter_recommendations,
    render_recommendation_history,
)
from dashboard.data_health_components import render_data_health_strip
from dashboard.manual_live_planner_components import build_manual_live_preview
from services.dashboard_read_models.dashboard_decision_history_view_v1 import (
    DashboardDecisionHistoryRowV1,
    DashboardDecisionHistoryViewV1,
)
from services.contracts.task9_live_paper_certification_progress_v1 import (
    Task9LivePaperCertificationProgressV1,
    Task9MarketProgressV1,
)
from services.dashboard_publication import (
    DashboardPublicationEnvelopeV1,
    DashboardPublicationSnapshotV1,
)
from services.dashboard_read_models import (
    DashboardApplicationViewV1,
    DashboardManualLivePlannerStateV1,
    DashboardMarketStateV1,
    DashboardPortfolioViewV1,
)
from services.dashboard_read_models.dashboard_runtime_operations_view_v1 import (
    DashboardComponentHealthViewV1,
    DashboardRuntimeOperationsViewV1,
)


NOW = datetime(2026, 8, 8, 10, 0, tzinfo=timezone.utc)


def market(name: str) -> DashboardMarketStateV1:
    return DashboardMarketStateV1(
        market=name, symbol=name, observed_at=NOW, market_status="CLOSED",
        data_status="PERSISTED", freshness_status="STALE",
    )


def progress(completed: int = 4) -> Task9LivePaperCertificationProgressV1:
    return Task9LivePaperCertificationProgressV1(
        nifty=Task9MarketProgressV1("NIFTY", 100, completed, 2, 3, 2, 1),
        sensex=Task9MarketProgressV1("SENSEX", 100, 7, 1, 4, 4, 0),
        replay_excluded=9, duplicate_excluded=2, invalid_excluded=1,
        unresolved=3, certification_complete=False,
    )


def portfolio() -> DashboardPortfolioViewV1:
    return DashboardPortfolioViewV1(
        portfolio_id="paper-1", trading_day_id="2026-08-08", updated_at=NOW,
        starting_capital=100000, available_cash=90000, reserved_capital=10000,
        deployed_capital=0, committed_capital=10000, realized_net_pnl=125,
        unrealized_pnl=0, total_pnl=125, total_equity=100125,
        open_position_count=0, pending_plan_count=0, concurrent_trade_count=0,
        aggregate_committed_risk=900, event_sequence=11,
    )


def view(view_id: str = "view-1") -> DashboardApplicationViewV1:
    return DashboardApplicationViewV1(
        view_id=view_id, generated_at=NOW, market_session_state="MARKET_CLOSED",
        nifty_market=market("NIFTY"), sensex_market=market("SENSEX"),
        selected_market="NIFTY", selected_market_rationale=("Higher certified score.",),
        rejected_market_rationale=("SENSEX confidence was lower.",),
        portfolio=portfolio(), task9_certification_progress=progress(),
        manual_live_planner=DashboardManualLivePlannerStateV1(
            status="NOT_IMPLEMENTED", notice="Manual planning is isolated from PAPER state."
        ),
    )


def snapshot(value: DashboardApplicationViewV1, sequence: int) -> DashboardPublicationSnapshotV1:
    envelope = DashboardPublicationEnvelopeV1(
        publication_id=f"publication-{sequence}", publication_sequence=sequence,
        published_at=NOW, source_updated_at=NOW, publication_status="NO_ACTION",
        freshness_status="STALE", application_view=value,
    )
    return DashboardPublicationSnapshotV1(
        latest_envelope=envelope, last_successful_publication_at=NOW,
        last_attempted_publication_at=NOW, last_attempt_status="PUBLISHED",
        last_attempt_error=None, publication_count=sequence, failed_attempt_count=0,
    )


def test_unified_view_is_immutable_and_keeps_markets_and_progress_distinct():
    value = view()

    assert value.nifty_market.market == "NIFTY"
    assert value.sensex_market.market == "SENSEX"
    assert value.selected_market == "NIFTY"
    assert value.rejected_market_rationale == ("SENSEX confidence was lower.",)
    assert value.task9_certification_progress.nifty.completed_live_paper_trades == 4
    assert value.task9_certification_progress.nifty.no_trade_completed == 3
    assert value.task9_certification_progress.nifty.remaining_trade_count == 96
    with pytest.raises(FrozenInstanceError):
        value.market_session_state = "OPEN"  # type: ignore[misc]


def test_progress_and_manual_planner_cannot_contaminate_paper_portfolio_state():
    value = view()

    assert value.portfolio.starting_capital == 100000
    assert value.task9_certification_progress.nifty.completed_live_paper_trades == 4
    assert value.manual_live_planner.status == "NOT_IMPLEMENTED"
    assert value.execution_mode == "PAPER"
    assert value.live_execution_eligible is False
    assert value.broker_order_submission is False
    assert value.read_only is True


def test_missing_optional_history_and_health_are_safe_and_market_closed_preserves_data():
    value = view()

    assert value.paper_trade_history == ()
    assert value.recommendation_history is None
    assert value.runtime_operations is None
    assert value.market_session_state == "MARKET_CLOSED"
    assert value.portfolio.total_pnl == 125
    assert value.task9_certification_progress.certification_complete is False


def test_publication_sync_applies_only_newer_unified_view_and_preserves_last_good():
    state = {}
    first = view("view-1")
    second = view("view-2")

    assert synchronize_dashboard_publication(state, snapshot(first, 1)) is True
    assert state[APPLICATION_VIEW_STATE_KEY] is first
    assert synchronize_dashboard_publication(state, snapshot(second, 1)) is False
    assert state[APPLICATION_VIEW_STATE_KEY] is first
    assert synchronize_dashboard_publication(state, snapshot(second, 2)) is True
    assert state[APPLICATION_VIEW_STATE_KEY] is second

    failed = DashboardPublicationSnapshotV1(
        latest_envelope=snapshot(second, 2).latest_envelope, last_successful_publication_at=NOW,
        last_attempted_publication_at=NOW, last_attempt_status="FAILED_ATTEMPT_PRESERVED",
        last_attempt_error="adapter failed", publication_count=2, failed_attempt_count=1,
    )
    assert synchronize_dashboard_publication(state, failed) is False
    assert state[APPLICATION_VIEW_STATE_KEY] is second


def test_newer_legacy_envelope_preserves_last_good_application_view():
    state = {}
    first = view("view-a")
    replacement = view("view-b")
    assert synchronize_dashboard_publication(state, snapshot(first, 1)) is True

    legacy_envelope = DashboardPublicationEnvelopeV1(
        publication_id="legacy-2", publication_sequence=2, published_at=NOW,
        source_updated_at=NOW, publication_status="NO_ACTION", freshness_status="FRESH",
    )
    legacy_snapshot = DashboardPublicationSnapshotV1(
        latest_envelope=legacy_envelope, last_successful_publication_at=NOW,
        last_attempted_publication_at=NOW, last_attempt_status="PUBLISHED",
        last_attempt_error=None, publication_count=2, failed_attempt_count=0,
    )
    assert synchronize_dashboard_publication(state, legacy_snapshot) is True
    assert state[APPLICATION_VIEW_STATE_KEY] is first

    assert synchronize_dashboard_publication(state, snapshot(replacement, 3)) is True
    assert state[APPLICATION_VIEW_STATE_KEY] is replacement

def test_unified_view_rejects_wrong_market_or_nonpaper_safety_flags():
    with pytest.raises(ValueError, match="nifty_market"):
        DashboardApplicationViewV1(
            view_id="bad", generated_at=NOW, market_session_state="CLOSED",
            nifty_market=market("SENSEX"),
        )
    with pytest.raises(ValueError, match="read-only PAPER"):
        DashboardApplicationViewV1(
            view_id="bad", generated_at=NOW, market_session_state="CLOSED",
            broker_order_submission=True,
        )


def test_unified_boundary_has_no_provider_or_execution_calls():
    root = Path(__file__).resolve().parents[1]
    source = "\n".join(
        (root / path).read_text(encoding="utf-8")
        for path in (
            "services/dashboard_read_models/dashboard_application_view_v1.py",
            "services/dashboard_publication/dashboard_publication_envelope_v1.py",
            "dashboard/dashboard_publication_sync.py",
        )
    )

    for forbidden in (
        "Angel", "angel_", "submit_order", "execute_trade",
        "calculate_recommendation", "increment_task9", "sqlite3",
    ):
        assert forbidden not in source


def test_closed_offline_status_keeps_published_portfolio_and_progress_visible():
    class FakeStreamlit:
        def __init__(self): self.events = []
        def warning(self, value): self.events.append(("warning", value))
        def info(self, value): self.events.append(("info", value))
        def caption(self, value): self.events.append(("caption", value))
        def write(self, value): self.events.append(("write", value))
    st = FakeStreamlit()
    status = DashboardPublicationStatusViewV1(
        "publication-1", 1, "NO_ACTION", "STALE", NOW, NOW,
        "FAILED_ATTEMPT_PRESERVED", "provider unavailable", 2,
    )
    render_dashboard_status(st=st, status=status, application_view=view())

    assert ("warning", "MARKET CLOSED · LAST PUBLISHED STATE") in st.events
    assert any("No current actionable trade" in event[1] for event in st.events if event[0] == "info")
    assert any("Total P&L: 125.0" in event[1] for event in st.events if event[0] == "write")
    assert any("NIFTY 4/100" in event[1] for event in st.events if event[0] == "write")
    assert any("provider unavailable" in event[1] for event in st.events if event[0] == "write")


def test_status_labels_keep_stale_and_offline_independent():
    class FakeStreamlit:
        def __init__(self): self.events = []
        def warning(self, value): self.events.append(("warning", value))
        def info(self, value): self.events.append(("info", value))
        def caption(self, value): self.events.append(("caption", value))
        def write(self, value): self.events.append(("write", value))
    def status(freshness="FRESH", attempt="PUBLISHED", error=None):
        return DashboardPublicationStatusViewV1("pub", 1, "NO_ACTION", freshness, NOW, NOW, attempt, error, 0)
    def warnings(source, published):
        st = FakeStreamlit()
        render_dashboard_status(st=st, status=published, application_view=source)
        return [event[1] for event in st.events if event[0] == "warning"]

    closed = view()
    assert "OFFLINE / LAST GOOD STATE" not in warnings(closed, status("STALE"))
    assert "STALE DATA · published state shown for reference only." in warnings(closed, status("STALE"))
    assert "OFFLINE / LAST GOOD STATE" not in warnings(closed, status())

    runtime = DashboardRuntimeOperationsViewV1("runtime", "OFFLINE", NOW)
    both = warnings(replace(closed, runtime_operations=runtime), status("STALE"))
    assert "MARKET CLOSED · LAST PUBLISHED STATE" in both
    assert "OFFLINE / LAST GOOD STATE" in both
    assert "STALE DATA · published state shown for reference only." in both


def test_task9_certification_center_projects_published_progress_only():
    class FakeStreamlit:
        def __init__(self, events=None): self.events = [] if events is None else events
        def subheader(self, value): self.events.append(("subheader", value))
        def caption(self, value): self.events.append(("caption", value))
        def write(self, value): self.events.append(("write", value))
        def info(self, value): self.events.append(("info", value))
        def success(self, value): self.events.append(("success", value))
        def metric(self, label, value): self.events.append(("metric", label, value))
        def columns(self, count): return tuple(FakeStreamlit(self.events) for _ in range(count))
    st = FakeStreamlit()
    render_task9_certification_center(st=st, view=view())
    assert ("metric", "LIVE PAPER TRADE TARGET", "4 / 100") in st.events
    assert ("metric", "LIVE PAPER TRADE TARGET", "7 / 100") in st.events
    assert ("metric", "Remaining", "96") in st.events
    assert any("NO_TRADE separate" in item[1] for item in st.events if item[0] == "write")
    assert any("REPLAY EXCLUDED: 9" in item[1] for item in st.events if item[0] == "write")
    assert any("WAIT does not count toward the live PAPER trade target." == item[1] for item in st.events if item[0] == "write")
    assert ("info", "No active external-provider blocker is currently published.") in st.events
    assert not any("Provider incident analytics are unavailable" in item[1] for item in st.events if item[0] == "write")
    assert ("CERTIFICATION IN PROGRESS (published authority)",) in [(x[1],) for x in st.events if x[0] == "info"]


def test_task9_certification_center_renders_only_published_external_provider_evidence():
    class FakeStreamlit:
        def __init__(self, events=None): self.events = [] if events is None else events
        def subheader(self, value): self.events.append(("subheader", value))
        def caption(self, value): self.events.append(("caption", value))
        def write(self, value): self.events.append(("write", value))
        def info(self, value): self.events.append(("info", value))
        def success(self, value): self.events.append(("success", value))
        def metric(self, label, value): self.events.append(("metric", label, value))
        def columns(self, count): return tuple(FakeStreamlit(self.events) for _ in range(count))

    blocker = {
        "provider": "Angel",
        "endpoint": "historical_candle_data",
        "blocker_code": "HISTORICAL_DATA_RATE_LIMITED",
        "status": "ACTIVE",
        "last_failure_reason": "HISTORICAL-DATA_RATE_LIMITED",
        "last_probe_result": "RATE_LIMITED",
        "consecutive_rate_limit_count": 3,
        "occurrence_count": 4,
        "last_probe_at": NOW,
        "next_probe_not_before": NOW,
        "first_seen_at": NOW,
        "last_seen_at": NOW,
    }
    st = FakeStreamlit()
    render_task9_certification_center(
        st=st,
        view=replace(view(), external_provider_blocker=blocker),
    )
    writes = [item[1] for item in st.events if item[0] == "write"]
    assert ("subheader", "External Provider Evidence") in st.events
    assert any("HISTORICAL_DATA_RATE_LIMITED" in item and "ACTIVE" in item and "historical_candle_data" in item for item in writes)
    assert any("Consecutive rate limits: 3" in item and "Occurrences: 4" in item for item in writes)
    assert any("Next probe not before: 2026-08-08T10:00:00+00:00" in item for item in writes)
    source = (Path(__file__).resolve().parents[1] / "dashboard" / "task9_certification_components.py").read_text(encoding="utf-8")
    assert "view.external_provider_blocker" in source
    assert "open(" not in source and "Path(" not in source and ".json" not in source


def test_task9_certification_center_handles_missing_or_complete_progress():
    class Fake:
        def __init__(self): self.events=[]
        def subheader(self, v): self.events.append(("subheader", v))
        def info(self, v): self.events.append(("info", v))
        def caption(self, v): self.events.append(("caption", v))
        def write(self, v): self.events.append(("write", v))
        def success(self, v): self.events.append(("success", v))
        def columns(self, n): return tuple(self for _ in range(n))
        def metric(self, *v): self.events.append(("metric", *v))
    empty = DashboardApplicationViewV1(view_id="none", generated_at=NOW, market_session_state="CLOSED")
    st = Fake(); render_task9_certification_center(st=st, view=empty)
    assert ("info", "Task 9 certification progress has not been published.") in st.events
    complete_progress = Task9LivePaperCertificationProgressV1(
        nifty=Task9MarketProgressV1("NIFTY", 100, 100, 0, 0, 0, 0),
        sensex=Task9MarketProgressV1("SENSEX", 100, 100, 0, 0, 0, 0),
        replay_excluded=0, duplicate_excluded=0, invalid_excluded=0, unresolved=0, certification_complete=True,
    )
    st = Fake(); render_task9_certification_center(st=st, view=DashboardApplicationViewV1(view_id="done", generated_at=NOW, market_session_state="CLOSED", task9_certification_progress=complete_progress))
    assert ("success", "CERTIFICATION COMPLETE (published authority)") in st.events


def test_recommendation_history_is_separate_and_preserves_published_rows():
    class Fake:
        def __init__(self): self.events=[]
        def subheader(self, v): self.events.append(("subheader", v))
        def caption(self, v): self.events.append(("caption", v))
        def write(self, v): self.events.append(("write", v))
        def info(self, v): self.events.append(("info", v))
        def warning(self, v): self.events.append(("warning", v))
    rows = (
        DashboardDecisionHistoryRowV1("decision-call", NOW, "CALL", .8, 100),
        DashboardDecisionHistoryRowV1("decision-wait", NOW, "WAIT", None, None),
        DashboardDecisionHistoryRowV1("decision-no-trade", NOW, "NO_TRADE", .4, 99),
    )
    history = DashboardDecisionHistoryViewV1("history", NOW, rows, True, ("partial archive",))
    source = DashboardApplicationViewV1(view_id="history", generated_at=NOW, market_session_state="CLOSED", recommendation_history=history)
    st = Fake(); render_recommendation_history(st=st, view=source)
    writes = [event[1] for event in st.events if event[0] == "write"]
    assert any("Action: CALL" in item and "does not" not in item for item in writes)
    assert any("Action: WAIT" in item for item in writes)
    assert any("Action: NO_TRADE" in item for item in writes)
    assert any("Source updated" in item for item in writes)
    assert any("truncated" in event[1] for event in st.events if event[0] == "warning")
    assert filter_recommendations(rows, action="WAIT") == (rows[1],)
    assert source.recommendation_history is history


def test_recommendation_history_missing_and_empty_are_safe():
    class Fake:
        def __init__(self): self.events=[]
        def subheader(self, v): self.events.append(("subheader", v))
        def caption(self, v): self.events.append(("caption", v))
        def write(self, v): self.events.append(("write", v))
        def info(self, v): self.events.append(("info", v))
        def warning(self, v): self.events.append(("warning", v))
    st=Fake(); render_recommendation_history(st=st, view=DashboardApplicationViewV1(view_id="none", generated_at=NOW, market_session_state="CLOSED"))
    assert ("info", "Certified recommendation history has not been published.") in st.events
    st=Fake(); history=DashboardDecisionHistoryViewV1("history", NOW)
    render_recommendation_history(st=st, view=DashboardApplicationViewV1(view_id="empty-history", generated_at=NOW, market_session_state="CLOSED", recommendation_history=history))
    assert ("info", "No published recommendation rows are available.") in st.events


def test_data_health_strip_uses_published_health_without_clock_or_provider():
    class Fake:
        def __init__(self, events=None): self.events=[] if events is None else events
        def subheader(self, v): self.events.append(("subheader", v))
        def write(self, v): self.events.append(("write", v))
        def warning(self, v): self.events.append(("warning", v))
        def columns(self, n): return tuple(Fake(self.events) for _ in range(n))
    st=Fake()
    status=DashboardPublicationStatusViewV1("pub", 1, "NO_ACTION", "STALE", NOW, NOW, "PUBLISHED", None, 0)
    render_data_health_strip(st=st, view=view(), publication_status=status)
    writes=[event[1] for event in st.events if event[0]=="write"]
    assert any("NIFTY: PERSISTED / STALE" in item for item in writes)
    assert any("SENSEX: PERSISTED / STALE" in item for item in writes)
    assert any("Overall display state: REFERENCE ONLY" in item for item in writes)
    assert any("Option quote freshness: Unavailable" in item for item in writes)


@pytest.mark.parametrize("runtime_status", ("OFFLINE", "FAILED", "UNAVAILABLE"))
def test_data_health_runtime_failure_is_reference_only(runtime_status):
    class Fake:
        def __init__(self, events=None): self.events=[] if events is None else events
        def subheader(self, v): self.events.append(("subheader", v))
        def write(self, v): self.events.append(("write", v))
        def warning(self, v): self.events.append(("warning", v))
        def columns(self, n): return tuple(Fake(self.events) for _ in range(n))
    runtime = DashboardRuntimeOperationsViewV1("runtime", runtime_status, NOW, freshness_status="FRESH", warnings=("published warning",))
    source = DashboardApplicationViewV1(view_id="healthy-markets", generated_at=NOW, market_session_state="OPEN", nifty_market=DashboardMarketStateV1("NIFTY", "NIFTY", NOW, "OPEN", "READY", "FRESH"), sensex_market=DashboardMarketStateV1("SENSEX", "SENSEX", NOW, "OPEN", "READY", "FRESH"), selected_market="NIFTY", runtime_operations=runtime)
    st=Fake(); render_data_health_strip(st=st, view=source, publication_status=DashboardPublicationStatusViewV1("pub", 1, "READY", "FRESH", NOW, NOW, "PUBLISHED", None, 0))
    assert any("Overall display state: REFERENCE ONLY" in event[1] for event in st.events if event[0] == "write")
    assert ("warning", "Runtime warning: published warning") in st.events


def test_manual_live_preview_isolated_and_validates_input():
    source = view()
    preview = build_manual_live_preview(view=source, capital=1000)
    assert preview.status == "NO_PUBLISHED_PLAN"
    assert preview.planning_only is True
    assert preview.broker_order_submission is False
    assert preview.live_execution_eligible is False
    assert source.portfolio.total_equity == 100125
    assert source.task9_certification_progress.nifty.completed_live_paper_trades == 4
    with pytest.raises(ValueError, match="capital"):
        build_manual_live_preview(view=source, capital=0)
    with pytest.raises(ValueError, match="risk_budget"):
        build_manual_live_preview(view=source, capital=1000, risk_budget=1001)
