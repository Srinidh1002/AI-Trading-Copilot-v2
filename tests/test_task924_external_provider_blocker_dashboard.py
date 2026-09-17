from datetime import datetime, timezone

from dashboard.dashboard_read_model_state import get_task9_external_provider_blocker_view
from services.certification.task9_external_provider_blocker import Task9ExternalProviderBlockerStore
from services.dashboard_read_models.dashboard_application_view_v1 import DashboardApplicationViewV1


NOW=datetime(2026,8,10,13,5,tzinfo=timezone.utc)

def test_optional_read_only_blocker_projection_preserves_paper_view(tmp_path):
 store=Task9ExternalProviderBlockerStore(tmp_path); value=store.record("run",observed_at=NOW)
 view=get_task9_external_provider_blocker_view(persistence_root=tmp_path,official_run_id="run")
 app=DashboardApplicationViewV1("view",NOW,"READ_ONLY",external_provider_blocker=view)
 assert view["status"]=="ACTIVE" and view["last_failure_reason"]=="HISTORICAL-DATA_RATE_LIMITED" and set(view)=={"blocker_code","status","provider","endpoint","first_seen_at","last_seen_at","last_probe_at","last_probe_result","last_failure_reason","next_probe_not_before","occurrence_count","consecutive_rate_limit_count"}
 assert app.read_only is True and app.execution_mode=="PAPER" and app.live_execution_eligible is False and app.broker_order_submission is False
 assert store.load("run")==value

def test_missing_is_none_and_old_snapshot_remains_constructible(tmp_path):
 assert get_task9_external_provider_blocker_view(persistence_root=tmp_path,official_run_id="run") is None
 assert DashboardApplicationViewV1("view",NOW,"READ_ONLY").external_provider_blocker is None
