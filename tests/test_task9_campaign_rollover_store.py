from datetime import date,datetime,timezone
import pytest
from services.certification.task9_campaign_rollover_store import Task9CampaignRolloverStore
from services.contracts.task9_campaign_rollover_v1 import *

def receipt(status="PLANNED"):
 d=Task9CampaignRolloverDecisionV1("campaign", "ADVANCE_TO_NEXT_MARKET_DAY",date(2026,8,15),"run-1",date(2026,8,16),"run-2","NEXT")
 return Task9CampaignRolloverReceiptV1(d.rollover_id,d.campaign_id,d.previous_market_date,d.previous_official_run_id,d.target_market_date,d.target_official_run_id,d.action,status,"task9-runtime-config-"+"a"*64,"a"*64,d.reason_code,datetime(2026,8,15,tzinfo=timezone.utc))
def test_receipt_is_atomic_idempotent_restart_safe_and_monotonic(tmp_path):
 s=Task9CampaignRolloverStore(tmp_path); r=receipt(); assert s.save(r)==r and Task9CampaignRolloverStore(tmp_path).read(r.rollover_id)==r
 assert s.save(r)==r
 r=s.advance(r.rollover_id,"RUN_MANIFEST_PERSISTED",applied_at=r.applied_at); r=s.advance(r.rollover_id,"POINTER_UPDATED",applied_at=r.applied_at); assert s.advance(r.rollover_id,"APPLIED",applied_at=r.applied_at).status.value=="APPLIED"
 with pytest.raises(ValueError): s.save(receipt())
def test_receipt_corruption_and_identity_conflicts_are_visible(tmp_path):
 s=Task9CampaignRolloverStore(tmp_path); r=receipt(); s.save(r); changed=Task9CampaignRolloverReceiptV1(r.rollover_id,r.campaign_id,r.previous_market_date,r.previous_official_run_id,r.target_market_date,r.target_official_run_id,r.action,r.status,"task9-runtime-config-"+"b"*64,"b"*64,r.decision_reason,r.applied_at)
 with pytest.raises(ValueError): s.save(changed)
 (tmp_path/"campaign-rollovers"/"bad.json").write_text("not json")
 with pytest.raises(ValueError): s.get("bad")
