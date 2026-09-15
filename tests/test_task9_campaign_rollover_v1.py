from datetime import date
import pytest
from services.contracts.task9_campaign_rollover_v1 import *
from services.certification.task9_campaign_rollover import plan_task9_campaign_rollover
from services.certification.task9_campaign_index_builder import build_task9_campaign_index,append_task9_campaign_run_contribution
from services.contracts.task9_campaign_index_v1 import Task9CampaignRunContributionV1
from tests.test_task9_campaign_manifest_v1 import _manifest
from tests.test_task9_active_campaign_pointer_v1 import _pointer
def test_rollover_decision_requires_forward_identity():
 assert Task9CampaignRolloverDecisionV1("c","CONTINUE_CURRENT_RUN",date(2026,8,1),"r",date(2026,8,1),"r","OK").action is Task9CampaignRolloverAction.CONTINUE_CURRENT_RUN

def _index(*rows): return build_task9_campaign_index(campaign_id="campaign-1",campaign_manifest_ref="m",campaign_status="ACTIVE",contributions=rows)
def _row(run,n,s,day=date(2026,8,15),**analytics): return Task9CampaignRunContributionV1(day,run,"OFFICIAL_CERTIFICATION",n,s,**analytics)

def test_rollover_carries_totals_and_analytics_unchanged_then_appends_new_day():
 old=_row("day-1",7,5,wait_completed_count=2,no_trade_completed_count=3,unavailable_count=1,invalid_count=1,excluded_count=1,open_or_pending_count=1,reconciliation_pending_count=1)
 index=_index(old); pointer=_pointer(); decision=plan_task9_campaign_rollover(manifest=_manifest(),pointer=pointer,index=index,target_market_date=date(2026,8,16),requested_official_run_id="day-2")
 assert decision.action is Task9CampaignRolloverAction.ADVANCE_TO_NEXT_MARKET_DAY and (index.nifty_countable_total,index.sensex_countable_total)==(7,5)
 rebuilt=append_task9_campaign_run_contribution(index,_row("day-2",3,4,date(2026,8,16)))
 assert (rebuilt.nifty_countable_total,rebuilt.sensex_countable_total)==(10,9)
 assert rebuilt.market_day_entries[0].wait_completed_count==2 and rebuilt.market_day_entries[0].reconciliation_pending_count==1

@pytest.mark.parametrize("nifty,sensex,expected",[(100,100,"CAMPAIGN_NUMERIC_TARGET_MET"),(101,100,"CAMPAIGN_NUMERIC_TARGET_MET"),(100,101,"CAMPAIGN_NUMERIC_TARGET_MET"),(101,103,"CAMPAIGN_NUMERIC_TARGET_MET"),(100,99,"ADVANCE_TO_NEXT_MARKET_DAY"),(99,100,"ADVANCE_TO_NEXT_MARKET_DAY")])
def test_numeric_target_boundary_never_resets_partial_totals(nifty,sensex,expected):
 index=_index(_row("source",nifty,sensex)); pointer=_pointer(); d=plan_task9_campaign_rollover(manifest=_manifest(),pointer=pointer,index=index,target_market_date=date(2026,8,16),requested_official_run_id="r2")
 assert d.action.value==expected and (index.nifty_countable_total,index.sensex_countable_total)==(nifty,sensex)

@pytest.mark.parametrize("nifty,sensex",[(100,83),(72,100)])
def test_partial_market_completion_carries_forward(nifty,sensex):
 index=_index(_row("source",nifty,sensex)); d=plan_task9_campaign_rollover(manifest=_manifest(),pointer=_pointer(),index=index,target_market_date=date(2026,8,16),requested_official_run_id="r2")
 assert d.action is Task9CampaignRolloverAction.ADVANCE_TO_NEXT_MARKET_DAY
