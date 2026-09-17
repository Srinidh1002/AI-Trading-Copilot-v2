from tests.test_task9_campaign_index_builder import c
from services.certification.task9_campaign_index_builder import build_task9_campaign_index
def test_empty_and_analytics_only_index():
 x=build_task9_campaign_index(campaign_id="c",campaign_manifest_ref="m",campaign_status="ACTIVE",contributions=(c("a",0,0,wait_completed_count=2,no_trade_completed_count=3,unavailable_count=1),))
 assert (x.nifty_countable_total,x.sensex_countable_total,x.numeric_target_met)==(0,0,False)
