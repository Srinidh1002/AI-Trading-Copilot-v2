from datetime import datetime,timezone
from dataclasses import replace
from tests.test_task9_runtime_config_snapshot_v1 import _config
from tests.test_task9_campaign_manifest_v1 import _manifest
from tests.test_task9_active_campaign_pointer_v1 import _pointer
from services.certification.task9_campaign_manifest_store import Task9CampaignManifestStore
from services.certification.task9_active_campaign_pointer_store import Task9ActiveCampaignPointerStore
from services.certification.task9_campaign_preflight_bridge import build_task9_campaign_preflight_phase
def test_bridge_missing_and_persisted_authority(tmp_path):
 c=_config();m=_manifest(campaign_id=c.campaign_id,runtime_config_snapshot_id="task9-runtime-config-"+"a"*64,runtime_config_sha256="a"*64);p=_pointer(campaign_id=c.campaign_id,active_official_run_id=c.official_run_id,active_market_date=c.market_date,runtime_config_snapshot_id=m.runtime_config_snapshot_id,runtime_config_sha256=m.runtime_config_sha256)
 ms=Task9CampaignManifestStore(tmp_path);ps=Task9ActiveCampaignPointerStore(tmp_path);assert build_task9_campaign_preflight_phase(runtime_config=c,manifest_store=ms,pointer_store=ps,observed_at=datetime.now(timezone.utc)).blocking
 ms.save(m);ps.set(p,manifest=m);assert build_task9_campaign_preflight_phase(runtime_config=c,manifest_store=ms,pointer_store=ps,observed_at=datetime.now(timezone.utc)).status.value=="PASS"

def test_bridge_blocks_rollover_and_terminal_pointer_states(tmp_path):
 c=_config();m=_manifest(campaign_id=c.campaign_id,runtime_config_snapshot_id="task9-runtime-config-"+"a"*64,runtime_config_sha256="a"*64);p=_pointer(campaign_id=c.campaign_id,active_official_run_id=c.official_run_id,active_market_date=c.market_date,runtime_config_snapshot_id=m.runtime_config_snapshot_id,runtime_config_sha256=m.runtime_config_sha256)
 ms=Task9CampaignManifestStore(tmp_path);ps=Task9ActiveCampaignPointerStore(tmp_path);ms.save(m);ps.set(p,manifest=m);now=datetime.now(timezone.utc)
 assert build_task9_campaign_preflight_phase(runtime_config=_config(market_date=c.market_date.replace(day=c.market_date.day+1),official_run_id="r2"),manifest_store=ms,pointer_store=ps,observed_at=now).reason_code=="ROLLOVER_REQUIRED"
 ps.set(replace(p,status="PAUSED"),manifest=m);assert build_task9_campaign_preflight_phase(runtime_config=c,manifest_store=ms,pointer_store=ps,observed_at=now).reason_code=="CAMPAIGN_PAUSED"

def test_bridge_fails_closed_for_provenance_mismatch_and_corrupt_pointer(tmp_path):
 c=_config();sid="task9-runtime-config-"+"a"*64;m=_manifest(campaign_id=c.campaign_id,runtime_config_snapshot_id=sid,runtime_config_sha256="a"*64);p=_pointer(campaign_id=c.campaign_id,active_official_run_id=c.official_run_id,active_market_date=c.market_date,runtime_config_snapshot_id=sid,runtime_config_sha256="a"*64);ms=Task9CampaignManifestStore(tmp_path);ps=Task9ActiveCampaignPointerStore(tmp_path);ms.save(m);ps.set(p,manifest=m);now=datetime.now(timezone.utc)
 assert build_task9_campaign_preflight_phase(runtime_config=c,manifest_store=ms,pointer_store=ps,observed_at=now,runtime_config_snapshot_id="task9-runtime-config-"+"b"*64,runtime_config_sha256="b"*64).reason_code=="SNAPSHOT_HASH_MISMATCH"
 ps.path.write_text("not-json",encoding="utf8")
 assert build_task9_campaign_preflight_phase(runtime_config=c,manifest_store=ms,pointer_store=ps,observed_at=now).reason_code=="CORRUPT_AUTHORITATIVE_STATE"
