"""Task 9.15 restart certification for immutable published dashboard state."""
from dashboard.dashboard_navigation import (
    DEFAULT_DASHBOARD_PAGE,
    NAVIGATION_STATE_KEY,
    normalize_dashboard_page,
)
from dashboard.dashboard_publication_sync import (
    APPLICATION_VIEW_STATE_KEY,
    PUBLICATION_ATTEMPT_ERROR_STATE_KEY,
    PUBLICATION_ATTEMPT_STATUS_STATE_KEY,
    synchronize_dashboard_publication,
)
from dashboard.dashboard_read_model_state import get_application_view
from dashboard.data_health_components import _overall
from dashboard.dashboard_status_components import DashboardPublicationStatusViewV1
from services.dashboard_publication import (
    DashboardPublicationEnvelopeV1,
    DashboardPublicationSnapshotV1,
)
from tests.test_task915_dashboard_application_view import NOW, snapshot, view
from tests.test_task915_trade_now_components import position
from services.dashboard_read_models.dashboard_decision_history_view_v1 import (
    DashboardDecisionHistoryRowV1, DashboardDecisionHistoryViewV1,
)
from services.dashboard_read_models.dashboard_runtime_operations_view_v1 import (
    DashboardRuntimeOperationsViewV1,
)
from dataclasses import replace
from datetime import timedelta
import pytest


def test_fresh_session_recovers_exact_published_application_view_and_safety():
    published = view("restart-view")
    session_state = {}

    assert synchronize_dashboard_publication(session_state, snapshot(published, 1)) is True
    recovered = get_application_view(session_state)

    assert recovered is published
    assert recovered.portfolio is published.portfolio
    assert recovered.task9_certification_progress is published.task9_certification_progress
    assert recovered.paper_trade_history == published.paper_trade_history
    assert recovered.recommendation_history is published.recommendation_history
    assert recovered.execution_mode == "PAPER"
    assert recovered.broker_order_submission is False
    assert recovered.live_execution_eligible is False
    assert recovered.read_only is True
    assert normalize_dashboard_page(session_state.get(NAVIGATION_STATE_KEY)) == DEFAULT_DASHBOARD_PAGE


def test_newer_legacy_or_failed_attempt_preserves_last_good_restart_view():
    published = view("last-good")
    state = {}
    synchronize_dashboard_publication(state, snapshot(published, 1))
    legacy = DashboardPublicationEnvelopeV1(
        publication_id="legacy-2", publication_sequence=2, published_at=NOW,
        source_updated_at=NOW, publication_status="NO_ACTION", freshness_status="STALE",
    )
    newer = DashboardPublicationSnapshotV1(
        latest_envelope=legacy, last_successful_publication_at=NOW,
        last_attempted_publication_at=NOW, last_attempt_status="FAILED_ATTEMPT_PRESERVED",
        last_attempt_error="runtime offline", publication_count=2, failed_attempt_count=1,
    )
    assert synchronize_dashboard_publication(state, newer) is True
    assert state[APPLICATION_VIEW_STATE_KEY] is published
    assert state[PUBLICATION_ATTEMPT_STATUS_STATE_KEY] == "FAILED_ATTEMPT_PRESERVED"
    assert state[PUBLICATION_ATTEMPT_ERROR_STATE_KEY] == "runtime offline"


def test_duplicate_and_out_of_order_publications_are_idempotent():
    newer, older = view("newer"), view("older")
    state = {}
    synchronize_dashboard_publication(state, snapshot(newer, 2))
    assert synchronize_dashboard_publication(state, snapshot(newer, 2)) is False
    assert synchronize_dashboard_publication(state, snapshot(older, 1)) is False
    assert state[APPLICATION_VIEW_STATE_KEY] is newer
    assert state[APPLICATION_VIEW_STATE_KEY].task9_certification_progress is newer.task9_certification_progress


def test_ui_planner_and_navigation_state_are_not_certification_recovery_state():
    published = view("published")
    first_session = {"manual_live_planner_capital": 1000, "manual_live_planner_risk": 100, NAVIGATION_STATE_KEY: "🧮 Manual Planner"}
    synchronize_dashboard_publication(first_session, snapshot(published, 1))
    restarted_session = {}
    synchronize_dashboard_publication(restarted_session, snapshot(published, 1))
    assert "manual_live_planner_capital" not in restarted_session
    assert "manual_live_planner_risk" not in restarted_session
    assert normalize_dashboard_page(restarted_session.get(NAVIGATION_STATE_KEY)) == DEFAULT_DASHBOARD_PAGE
    assert get_application_view(restarted_session) is published


def test_restart_preserves_explicit_progress_portfolio_position_and_history_values():
    active = position()
    closed = replace(position(), paper_trade_id="closed-1", is_terminal=True, lifecycle_state="CLOSED", lifecycle_display_group="TERMINAL")
    history = DashboardDecisionHistoryViewV1("history", NOW, (DashboardDecisionHistoryRowV1("decision-1", NOW, "WAIT", .33, 101),), True, ("archive partial",))
    published = replace(view("complete-evidence"), active_paper_position=active, paper_trade_history=(closed,), recommendation_history=history)
    state = {}; synchronize_dashboard_publication(state, snapshot(published, 1)); recovered = get_application_view(state)
    progress = recovered.task9_certification_progress
    assert (progress.nifty.completed_live_paper_trades, progress.nifty.target_trade_count, progress.nifty.remaining_trade_count, progress.nifty.pending_entered_trades, progress.nifty.no_trade_completed, progress.nifty.no_trade_passed, progress.nifty.no_trade_failed) == (4, 100, 96, 2, 3, 2, 1)
    assert (progress.sensex.completed_live_paper_trades, progress.sensex.target_trade_count, progress.sensex.remaining_trade_count, progress.sensex.pending_entered_trades, progress.sensex.no_trade_completed, progress.sensex.no_trade_passed, progress.sensex.no_trade_failed) == (7, 100, 93, 1, 4, 4, 0)
    assert (progress.replay_excluded, progress.duplicate_excluded, progress.invalid_excluded, progress.unresolved, progress.certification_complete) == (9, 2, 1, 3, False)
    assert recovered.portfolio.to_dict() == published.portfolio.to_dict()
    assert recovered.active_paper_position.paper_trade_id == "paper-1"
    assert tuple(item.paper_trade_id for item in recovered.paper_trade_history) == ("closed-1",)
    assert recovered.recommendation_history.to_dict() == history.to_dict()


@pytest.mark.parametrize("runtime_status", ("OFFLINE", "FAILED"))
def test_closed_stale_and_runtime_failure_remain_reference_only_after_restart(runtime_status):
    runtime = DashboardRuntimeOperationsViewV1("runtime", runtime_status, NOW, freshness_status="STALE")
    published = replace(view("closed"), runtime_operations=runtime)
    state = {}; synchronize_dashboard_publication(state, snapshot(published, 1)); recovered = get_application_view(state)
    status = DashboardPublicationStatusViewV1("pub", 1, "NO_ACTION", "STALE", NOW, NOW, "PUBLISHED", None, 0)
    assert recovered.market_session_state == "MARKET_CLOSED"
    assert _overall(recovered, status) == "REFERENCE ONLY"


def test_midnight_restart_and_duplicate_do_not_reset_or_duplicate_published_evidence():
    published = view("midnight")
    envelope = snapshot(published, 1).latest_envelope
    midnight = replace(envelope, published_at=NOW + timedelta(days=1), source_updated_at=NOW + timedelta(days=1))
    snap = DashboardPublicationSnapshotV1(midnight, midnight.published_at, midnight.published_at, "PUBLISHED", None, 1, 0)
    state = {}; synchronize_dashboard_publication(state, snap); before = get_application_view(state)
    assert synchronize_dashboard_publication(state, snap) is False
    after = get_application_view(state)
    assert after.task9_certification_progress.to_dict() == before.task9_certification_progress.to_dict()
    assert after.paper_trade_history == before.paper_trade_history


def test_unsafe_application_contracts_fail_closed_before_publication():
    with pytest.raises(ValueError, match="read-only PAPER"):
        replace(view(), broker_order_submission=True)
    with pytest.raises(ValueError, match="PAPER"):
        replace(view(), execution_mode="LIVE")
    with pytest.raises(ValueError, match="read-only PAPER"):
        replace(view(), read_only=False)
    with pytest.raises(ValueError, match="false"):
        replace(view(), live_execution_eligible=True)
