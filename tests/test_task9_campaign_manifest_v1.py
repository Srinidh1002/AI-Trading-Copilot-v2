from dataclasses import FrozenInstanceError
from datetime import date
import pytest
from services.contracts.task9_campaign_manifest_v1 import *
SHA="a"*64;SID="task9-runtime-config-"+SHA
def _manifest(**k):
 d=dict(campaign_id="campaign-1",campaign_version="1",campaign_status="ACTIVE",created_market_date=date(2026,8,15),registry_root="task9/registry",campaign_root="task9/campaign-1",runtime_config_snapshot_id=SID,runtime_config_sha256=SHA);d.update(k);return Task9CampaignManifestV1(**d)
def test_manifest_invariants_targets_and_numeric_completion():
 m=_manifest();assert m.numeric_target_met(nifty_count=100,sensex_count=100) and not m.numeric_target_met(nifty_count=100,sensex_count=99) and m.numeric_target_met(nifty_count=101,sensex_count=200)
 assert m.campaign_status is Task9CampaignStatus.ACTIVE
 with pytest.raises(FrozenInstanceError):m.campaign_id="x"
 assert Task9CampaignManifestV1.from_dict(m.to_dict())==m
 for n,v in (("target_nifty_count",99),("target_sensex_count",99),("replay_counts_toward_target",True),("diagnostic_counts_toward_target",True),("wait_counts_toward_target",True),("no_trade_counts_toward_target",True),("execution_mode","LIVE"),("broker_order_submission",True),("live_execution_eligible",True)):
  with pytest.raises(ValueError):_manifest(**{n:v})
