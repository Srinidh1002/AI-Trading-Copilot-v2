from datetime import datetime,timezone
from services.certification.task9_live_paper_certification_launcher import load_or_create_task9_run_manifest
from services.certification.task9_same_day_transition_authority import evaluate_task9_same_day_transition

NOW=datetime(2026,8,14,10,0,tzinfo=timezone.utc)
def test_fresh_official_root_is_ready_when_diagnostic_has_no_position(tmp_path):
 diagnostic=tmp_path/"diagnostic"; official=tmp_path/"official"
 load_or_create_task9_run_manifest(persistence_root=diagnostic,official_run_id="diag",started_at=NOW,run_classification="DIAGNOSTIC_NON_COUNTING")
 result=evaluate_task9_same_day_transition(diagnostic_root=diagnostic,diagnostic_run_id="diag",official_root=official,official_run_id="official")
 assert result.status=="READY"
def test_transition_rejects_same_or_nonfresh_root(tmp_path):
 diagnostic=tmp_path/"diagnostic"; load_or_create_task9_run_manifest(persistence_root=diagnostic,official_run_id="diag",started_at=NOW,run_classification="DIAGNOSTIC_NON_COUNTING")
 assert evaluate_task9_same_day_transition(diagnostic_root=diagnostic,diagnostic_run_id="diag",official_root=diagnostic,official_run_id="official").status=="INVALID_DIAGNOSTIC_STATE"
