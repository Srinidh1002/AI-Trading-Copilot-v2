from datetime import date,datetime,timezone
import pytest
from services.contracts.task9_campaign_index_v1 import Task9CampaignRunContributionV1
from services.certification.task9_campaign_index_builder import *
def c(run,n=0,s=0,kind="OFFICIAL_CERTIFICATION",**k):return Task9CampaignRunContributionV1(date(2026,8,15),run,kind,n,s,**k)
def test_contributions_totals_and_duplicates():
 x=build_task9_campaign_index(campaign_id="c",campaign_manifest_ref="m",campaign_status="ACTIVE",contributions=(c("n",1,0),c("s",0,2)))
 assert (x.nifty_countable_total,x.sensex_countable_total)==(1,2)
 assert append_task9_campaign_run_contribution(x,c("n",1,0))==x
 with pytest.raises(ValueError):append_task9_campaign_run_contribution(x,c("n",2,0))
 with pytest.raises(ValueError):c("d",1,0,"DIAGNOSTIC_NON_COUNTING")
 assert not build_task9_campaign_index(campaign_id="c",campaign_manifest_ref="m",campaign_status="ACTIVE",contributions=(c("a",100,99),)).numeric_target_met
