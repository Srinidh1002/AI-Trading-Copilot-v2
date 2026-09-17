from dataclasses import FrozenInstanceError
from datetime import date,datetime,timezone
import pytest
from services.contracts.task9_campaign_manifest_v1 import *
SHA="a"*64;SID="task9-runtime-config-"+SHA
def _pointer(**k):
 d=dict(campaign_id="campaign-1",campaign_manifest_ref="task9/registry/campaign-1.json",campaign_root="task9/campaign-1",registry_root="task9/registry",active_market_date=date(2026,8,15),active_official_run_id="run-1",run_classification="OFFICIAL_CERTIFICATION",runtime_config_snapshot_id=SID,runtime_config_sha256=SHA,updated_at=datetime(2026,8,15,tzinfo=timezone.utc),status="ACTIVE");d.update(k);return Task9ActiveCampaignPointerV1(**d)
def test_pointer_requires_official_run_is_immutable_and_round_trips():
 p=_pointer();assert Task9ActiveCampaignPointerV1.from_dict(p.to_dict())==p
 with pytest.raises(FrozenInstanceError):p.status="PAUSED"
 for n,v in (("run_classification","DIAGNOSTIC_NON_COUNTING"),("active_official_run_id",""),("runtime_config_sha256","bad")):
  with pytest.raises(ValueError):_pointer(**{n:v})
 assert _pointer(active_market_date=date(2026,8,16)).campaign_id==p.campaign_id
