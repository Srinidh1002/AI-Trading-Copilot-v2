from datetime import date,datetime,timezone
import pytest
from services.certification.task9_live_paper_certification_launcher import Task9LivePaperRunManifestV1,load_or_create_task9_run_manifest,read_task9_run_manifest
from services.certification.task9_campaign_rollover_target_run import validate_task9_rollover_target_run_manifest

def test_rollover_identity_is_durable_and_legacy_manifest_stays_readable(tmp_path):
 sha="a"*64; sid="task9-runtime-config-"+sha; now=datetime(2026,8,16,tzinfo=timezone.utc)
 new=Task9LivePaperRunManifestV1("run-2",now,runtime_config_snapshot_id=sid,runtime_config_sha256=sha,campaign_id="campaign-1",market_date=date(2026,8,16))
 assert validate_task9_rollover_target_run_manifest(run_manifest=new,campaign_id="campaign-1",market_date=date(2026,8,16),official_run_id="run-2",runtime_config_snapshot_id=sid,runtime_config_sha256=sha)
 (tmp_path/"task9-live-paper-run.json").write_text('{"official_run_id":"old","official_start_at":"2026-08-15T00:00:00+00:00","run_classification":"OFFICIAL_CERTIFICATION","execution_mode":"PAPER","broker_order_submission":false,"live_execution_eligible":false}')
 legacy=load_or_create_task9_run_manifest(persistence_root=tmp_path,official_run_id="old",started_at=now)
 assert legacy.campaign_id is None and legacy.market_date is None
 with pytest.raises(ValueError): validate_task9_rollover_target_run_manifest(run_manifest=legacy,campaign_id="campaign-1",market_date=date(2026,8,16),official_run_id="old",runtime_config_snapshot_id=sid,runtime_config_sha256=sha)

def test_restart_read_preserves_new_rollover_authority(tmp_path):
 sha="a"*64; sid="task9-runtime-config-"+sha; now=datetime(2026,8,16,tzinfo=timezone.utc)
 first=load_or_create_task9_run_manifest(persistence_root=tmp_path,official_run_id="run-2",started_at=now,runtime_config_snapshot_id=sid,runtime_config_sha256=sha,campaign_id="campaign-1",market_date=date(2026,8,16))
 assert read_task9_run_manifest(persistence_root=tmp_path)==first
 assert load_or_create_task9_run_manifest(persistence_root=tmp_path,official_run_id="run-2",started_at=now,runtime_config_snapshot_id=sid,runtime_config_sha256=sha,campaign_id="campaign-1",market_date=date(2026,8,16))==first
